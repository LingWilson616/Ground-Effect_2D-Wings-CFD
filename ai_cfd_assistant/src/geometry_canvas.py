"""Interactive 2D geometry canvas with pan, zoom, grid, and point creation.

Features (per prompt.txt):
- Left-drag: pan canvas
- Scroll wheel: zoom in/out
- Click: create geometry based on current tool
- 10mm grid with adaptive subdivision
- Coordinate display
"""

from __future__ import annotations
from enum import Enum, auto
import numpy as np
from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont,
    QPainterPath, QBrush, QMouseEvent, QWheelEvent,
)


class GeoTool(Enum):
    POINT = auto()
    LINE = auto()
    SPLINE = auto()
    CREATE = auto()
    DELETE = auto()
    MOVE = auto()
    SELECT = auto()  # default — pan mode


class InteractiveGeometryCanvas(QWidget):
    """Zoomable, pannable 2D CAD canvas mimicking engineering sketchpad."""

    point_created = Signal(float, float)
    mouse_moved = Signal(float, float)
    status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #ececec;")

        self.world_w = 3000.0
        self.world_h = 2000.0

        self._offset_x = 0.0
        self._offset_y = 0.0
        self._scale = 1.0

        self._panning = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._pan_start_offset_x = 0.0
        self._pan_start_offset_y = 0.0
        self._drag_threshold = 5
        self._mouse_press_pos = None
        self._released_without_drag = False
        self._spline_finished = False  # ignore stray release after double-click

        # Line drawing state
        self._line_start = None  # waiting for second point
        self._pending_points = []  # for spline

        # Tool system
        self._current_tool = GeoTool.SELECT

        # Geometry elements
        self.points: list[tuple[float, float]] = []
        self.lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self.splines: list[list[tuple[float, float]]] = []  # interpolated spline points
        self.airfoil_x = None
        self.airfoil_y = None
        self.airfoil_name = ""

        self._grid_base_mm = 100.0
        self._grid_minor_mm = 10.0

        self._bg_color = QColor(236, 236, 236)
        self._grid_major = QColor(190, 190, 190)
        self._grid_minor = QColor(220, 220, 220)
        self._axis_color = QColor(100, 100, 100)
        self._airfoil_fill = QColor(31, 111, 235, 60)
        self._airfoil_stroke = QColor(31, 111, 235)
        self._point_color = QColor(220, 50, 50)
        self._line_preview = QColor(31, 111, 235, 150)
        self._point_radius = 5.0
        self._initial_fit_done = False

        self._fit_to_widget()

    # ===== Tool API =====

    @property
    def current_tool(self):
        return self._current_tool

    def set_tool(self, tool: GeoTool):
        self._current_tool = tool
        self._line_start = None
        self._pending_points = []
        names = {
            GeoTool.SELECT: "选择/平移 — 点击操作 | 长按拖动平移 | 滚轮缩放",
            GeoTool.POINT: "点工具 — 点击画布创建点 | 长按拖动平移",
            GeoTool.LINE: "直线工具 — 点击两点创建直线 | 长按拖动平移",
            GeoTool.SPLINE: "样条线 — 点击多点，双击完成 | 长按拖动平移",
            GeoTool.CREATE: "创建 — 点击创建几何元素 | 长按拖动平移",
            GeoTool.DELETE: "删除 — 点击删除最近元素 | 长按拖动平移",
            GeoTool.MOVE: "移动 — 拖动几何元素",
        }
        self.status_changed.emit(names.get(tool, ""))
        self.update()

    # ===== Coordinate transforms =====

    def _world_to_widget(self, wx: float, wy: float) -> tuple[float, float]:
        """World (mm, origin bottom-left) → widget pixel (origin top-left)."""
        px = wx * self._scale + self._offset_x
        py = self.height() - (wy * self._scale + self._offset_y)
        return px, py

    def _widget_to_world(self, px: float, py: float) -> tuple[float, float]:
        """Widget pixel → world mm."""
        wx = (px - self._offset_x) / self._scale
        wy = ((self.height() - py) - self._offset_y) / self._scale
        return wx, wy

    def _fit_to_widget(self):
        """Fit entire world canvas into widget view."""
        w = self.width() or 800
        h = self.height() or 600
        margin = 40
        sx = (w - 2 * margin) / self.world_w
        sy = (h - 2 * margin) / self.world_h
        self._scale = min(sx, sy)
        self._offset_x = margin
        self._offset_y = margin
        self._clamp_view()

    # ===== Event handlers =====

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._initial_fit_done:
            self._fit_to_widget()
            self._initial_fit_done = True

    def mousePressEvent(self, event: QMouseEvent):
        self._mouse_press_pos = event.position()
        self._released_without_drag = False

        if event.button() == Qt.LeftButton:
            # Start potential pan — will become click if released without moving
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            self._pan_start_offset_x = self._offset_x
            self._pan_start_offset_y = self._offset_y

        elif event.button() == Qt.MiddleButton:
            self._fit_to_widget()
            self.status_changed.emit("视图已重置")

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            dx = event.position().x() - self._pan_start_x
            dy = event.position().y() - self._pan_start_y
            if abs(dx) > self._drag_threshold or abs(dy) > self._drag_threshold:
                if not self._panning:
                    self._panning = True
                    self.setCursor(Qt.ClosedHandCursor)
                self._offset_x = self._pan_start_offset_x + dx
                self._offset_y = self._pan_start_offset_y - dy
                self._clamp_view()
                self.update()
        wx, wy = self._widget_to_world(event.position().x(), event.position().y())
        self.mouse_moved.emit(wx, wy)
        if self._line_start is not None:
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self._spline_finished:
                self._spline_finished = False
            elif not self._panning:
                self._execute_tool_action(event.position().x(), event.position().y())
            self._panning = False
            self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._current_tool == GeoTool.SPLINE:
            # First click of the double-click already added a point via mouseReleaseEvent.
            # Remove that extra point, then finish the spline with the remaining points.
            if self._pending_points:
                self._pending_points.pop()
            if len(self._pending_points) >= 2:
                curve = self._catmull_rom_spline(self._pending_points)
                self.splines.append(curve)
                self.status_changed.emit(
                    f"样条线完成: {len(self._pending_points)} 个控制点 → {len(curve)} 个插值点"
                )
                self._pending_points = []
                self._spline_finished = True  # block the trailing release event
            else:
                self.status_changed.emit("样条线至少需要2个点，请继续点击添加控制点")
            self.update()

    @staticmethod
    def _catmull_rom_spline(pts: list[tuple[float, float]], n_per_seg: int = 20) -> list[tuple[float, float]]:
        """Generate Catmull-Rom spline from control points.

        Uses centripetal parameterization for smooth, loop-free curves.
        """
        n = len(pts)
        if n < 2:
            return pts[:]

        # Duplicate endpoints for natural boundary condition
        p = [pts[0]] + pts + [pts[-1]]

        result = [pts[0]]
        for i in range(1, n):
            p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
            for t_idx in range(1, n_per_seg + 1):
                t = t_idx / n_per_seg
                # Catmull-Rom basis with tension 0.5
                tt = t * t
                ttt = tt * t
                x = 0.5 * (
                    (2 * p1[0]) +
                    (-p0[0] + p2[0]) * t +
                    (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * tt +
                    (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * ttt
                )
                y = 0.5 * (
                    (2 * p1[1]) +
                    (-p0[1] + p2[1]) * t +
                    (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * tt +
                    (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * ttt
                )
                result.append((x, y))

        return result

    def _execute_tool_action(self, px: float, py: float):
        """Perform the current tool's action at the given widget pixel position."""
        wx, wy = self._widget_to_world(px, py)
        in_bounds = 0 <= wx <= self.world_w and 0 <= wy <= self.world_h
        if not in_bounds:
            self.status_changed.emit("点击位置超出幕布范围")
            return

        tool = self._current_tool
        if tool == GeoTool.SELECT or tool == GeoTool.POINT or tool == GeoTool.CREATE:
            self.points.append((wx, wy))
            self.point_created.emit(wx, wy)
            self.status_changed.emit(f"创建点: ({wx:.1f}, {wy:.1f}) mm")
        elif tool == GeoTool.LINE:
            if self._line_start is None:
                self._line_start = (wx, wy)
                self.status_changed.emit(f"直线起点: ({wx:.1f}, {wy:.1f}) — 点击终点")
            else:
                self.lines.append((self._line_start, (wx, wy)))
                self.status_changed.emit(
                    f"直线: ({self._line_start[0]:.1f},{self._line_start[1]:.1f}) → ({wx:.1f},{wy:.1f})"
                )
                self._line_start = None
        elif tool == GeoTool.SPLINE:
            self._pending_points.append((wx, wy))
            n = len(self._pending_points)
            self.status_changed.emit(f"样条线控制点 {n}: ({wx:.1f}, {wy:.1f}) — 继续点击，双击完成")
        elif tool == GeoTool.DELETE:
            if self.points:
                removed = self.points.pop()
                self.status_changed.emit(f"已删除点: ({removed[0]:.1f}, {removed[1]:.1f})")
            elif self.lines:
                removed = self.lines.pop()
                self.status_changed.emit("已删除最近一条直线")
            elif self.splines:
                removed = self.splines.pop()
                self.status_changed.emit(f"已删除样条线 ({len(removed)} 个插值点)")
            elif self._pending_points:
                self._pending_points.pop()
                n = len(self._pending_points)
                self.status_changed.emit(f"已删除控制点，剩余 {n}" + (" 个 — 双击完成" if n > 0 else " 个，已取消"))
            else:
                self.status_changed.emit("没有可删除的元素")
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        """Zoom centered on mouse, clamped."""
        mx, my = event.position().x(), event.position().y()

        # World point under mouse before zoom
        wx = (mx - self._offset_x) / self._scale
        wy = ((self.height() - my) - self._offset_y) / self._scale

        if event.angleDelta().y() > 0:
            s = 1.15
        else:
            s = 1.0 / 1.15

        new_scale = self._scale * s
        new_scale = max(0.08, min(new_scale, 8.0))  # clamp zoom range
        s = new_scale / self._scale

        self._offset_x = mx - wx * new_scale
        self._offset_y = (self.height() - my) - wy * new_scale
        self._scale = new_scale
        self._clamp_view()
        self.update()

    def _clamp_view(self):
        """Clamp pan so canvas (0,0)-(3000,2000) is never fully off-screen."""
        w, h = self.width(), self.height()

        # World coords of widget corners
        wl, wb = self._widget_to_world(0, h)      # top-left in world
        wr, wt = self._widget_to_world(w, 0)       # bottom-right in world

        # Prevent panning too far left: world right edge must be visible
        # wr (rightmost visible world x) should be >= 0
        if wr < 0:
            # Shift view right
            self._offset_x += (0 - wr) * self._scale

        # Prevent panning too far right: world left edge must be visible
        if wl > self.world_w:
            self._offset_x += (self.world_w - wl) * self._scale

        # Prevent panning too far down: world top edge must be visible
        if wt < 0:
            self._offset_y += (0 - wt) * self._scale

        # Prevent panning too far up: world bottom edge must be visible
        if wb > self.world_h:
            self._offset_y += (self.world_h - wb) * self._scale

        # If canvas is smaller than widget (zoomed out), center it
        canvas_px_w = self.world_w * self._scale
        canvas_px_h = self.world_h * self._scale
        if canvas_px_w < w:
            self._offset_x = (w - canvas_px_w) / 2
        if canvas_px_h < h:
            self._offset_y = (h - canvas_px_h) / 2

    # ===== Drawing =====

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        self._draw_background(p)
        self._draw_grid(p)
        self._draw_axes(p)
        self._draw_airfoil(p)
        self._draw_geometry_elements(p)
        self._draw_tool_indicator(p)

    def _draw_tool_indicator(self, p: QPainter):
        """Show current tool name in corner."""
        p.setPen(QPen(QColor(120, 120, 120), 1))
        font = QFont("Segoe UI", 10)
        p.setFont(font)
        tool_names = {
            GeoTool.SELECT: "选择/平移",
            GeoTool.POINT: "点",
            GeoTool.LINE: "直线",
            GeoTool.SPLINE: "样条线",
            GeoTool.CREATE: "创建",
            GeoTool.DELETE: "删除",
            GeoTool.MOVE: "移动",
        }
        name = tool_names.get(self._current_tool, "")
        p.drawText(self.width() - 200, self.height() - 12, f"工具: {name} | 点击操作 | 长按平移")

    def _draw_background(self, p: QPainter):
        """Fill widget background and draw canvas border rectangle."""
        # Widget background (outside canvas)
        p.fillRect(self.rect(), QColor(200, 200, 200))

        # Canvas area (light gray)
        left, top = self._world_to_widget(0, self.world_h)
        right, bottom = self._world_to_widget(self.world_w, 0)
        canvas_rect_x = min(left, right)
        canvas_rect_y = min(top, bottom)
        canvas_rect_w = abs(right - left)
        canvas_rect_h = abs(bottom - top)
        p.fillRect(int(canvas_rect_x), int(canvas_rect_y), int(canvas_rect_w), int(canvas_rect_h), self._bg_color)

        # Canvas border (bold)
        pen = QPen(QColor(130, 130, 130), 2.5)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(int(canvas_rect_x), int(canvas_rect_y), int(canvas_rect_w), int(canvas_rect_h))

    def _draw_grid(self, p: QPainter):
        """Draw double-level grid: minor (10mm) + major (100mm), clipped to canvas."""

        # Canvas pixel bounds
        x0_px, _ = self._world_to_widget(0, 0)
        x1_px, _ = self._world_to_widget(self.world_w, 0)
        _, y0_px = self._world_to_widget(0, 0)
        _, y1_px = self._world_to_widget(0, self.world_h)

        c_left = min(x0_px, x1_px)
        c_right = max(x0_px, x1_px)
        c_top = min(y0_px, y1_px)
        c_bottom = max(y0_px, y1_px)

        px_per_10mm = 10 * self._scale

        # Minor grid (10mm) — only if visible
        if px_per_10mm > 3:
            pen_minor = QPen(QColor(215, 215, 215), 0.3)
            p.setPen(pen_minor)
            wx = 0.0
            while wx <= self.world_w + 1e-6:
                px, _ = self._world_to_widget(wx, 0)
                if c_left <= int(px) <= c_right:
                    p.drawLine(int(px), int(c_top), int(px), int(c_bottom))
                wx += 10.0
            wy = 0.0
            while wy <= self.world_h + 1e-6:
                _, py = self._world_to_widget(0, wy)
                if c_top <= int(py) <= c_bottom:
                    p.drawLine(int(c_left), int(py), int(c_right), int(py))
                wy += 10.0

        # Major grid (100mm) — always visible
        pen_major = QPen(QColor(185, 185, 185), 0.7)
        p.setPen(pen_major)
        wx = 0.0
        while wx <= self.world_w + 1e-6:
            px, _ = self._world_to_widget(wx, 0)
            if c_left <= int(px) <= c_right:
                p.drawLine(int(px), int(c_top), int(px), int(c_bottom))
            wx += 100.0
        wy = 0.0
        while wy <= self.world_h + 1e-6:
            _, py = self._world_to_widget(0, wy)
            if c_top <= int(py) <= c_bottom:
                p.drawLine(int(c_left), int(py), int(c_right), int(py))
            wy += 100.0

    def _draw_axes(self, p: QPainter):
        """Draw XY axes along canvas edges (left edge = Y, bottom edge = X)."""
        # Pixel positions of canvas edges
        x0, y0 = self._world_to_widget(0, 0)           # origin (bottom-left)
        x1, y1 = self._world_to_widget(self.world_w, 0) # bottom-right
        _, y_top = self._world_to_widget(0, self.world_h) # top-left

        c_left = min(x0, x1)
        c_right = max(x0, x1)
        c_bottom = max(y0, y1)    # pixel y at world y=0 (bottom)
        c_top = min(y_top, y0)    # pixel y at world y=2000 (top)

        axis_color = QColor(80, 80, 80)
        thick_pen = QPen(axis_color, 2.5)
        thin_pen = QPen(axis_color, 1)

        # --- X axis: along bottom edge of canvas (y=0) ---
        p.setPen(thick_pen)
        p.drawLine(int(c_left), int(c_bottom), int(c_right + 15), int(c_bottom))
        # Arrow
        arrow_x = int(c_right + 15)
        arrow_y = int(c_bottom)
        p.drawLine(arrow_x, arrow_y, arrow_x - 10, arrow_y - 5)
        p.drawLine(arrow_x, arrow_y, arrow_x - 10, arrow_y + 5)
        p.drawLine(arrow_x - 10, arrow_y - 5, arrow_x - 10, arrow_y + 5)

        # X axis label
        font = QFont("Segoe UI", 11, QFont.Bold)
        p.setFont(font)
        p.setPen(QPen(axis_color, 1))
        p.drawText(arrow_x + 2, arrow_y + 5, "X")

        # X tick marks and labels (every 100mm, label every 500mm)
        font_sm = QFont("Segoe UI", 7)
        p.setFont(font_sm)
        p.setPen(thin_pen)
        wx = 0.0
        while wx <= self.world_w + 1e-6:
            tx, ty = self._world_to_widget(wx, 0)
            if c_left <= tx <= c_right:
                p.drawLine(int(tx), int(c_bottom), int(tx), int(c_bottom + 8))
                if wx > 0 and int(wx) % 500 == 0:
                    label = f"{int(wx)}" if wx == int(wx) else f"{wx:.0f}"
                    p.drawText(int(tx - 14), int(c_bottom + 20), label)
            wx += 100.0

        # --- Y axis: along left edge of canvas (x=0) ---
        p.setPen(thick_pen)
        p.drawLine(int(c_left), int(c_bottom + 5), int(c_left), int(c_top - 15))
        # Arrow
        arrow_x = int(c_left)
        arrow_y = int(c_top - 15)
        p.drawLine(arrow_x, arrow_y, arrow_x - 5, arrow_y + 10)
        p.drawLine(arrow_x, arrow_y, arrow_x + 5, arrow_y + 10)
        p.drawLine(arrow_x - 5, arrow_y + 10, arrow_x + 5, arrow_y + 10)

        # Y axis label
        font = QFont("Segoe UI", 11, QFont.Bold)
        p.setFont(font)
        p.setPen(QPen(axis_color, 1))
        p.drawText(arrow_x - 16, arrow_y + 20, "Y")

        # Y tick marks and labels (every 100mm, label every 500mm)
        font_sm = QFont("Segoe UI", 7)
        p.setFont(font_sm)
        p.setPen(thin_pen)
        wy = 0.0
        while wy <= self.world_h + 1e-6:
            tx, ty = self._world_to_widget(0, wy)
            if c_top <= ty <= c_bottom:
                p.drawLine(int(c_left - 8), int(ty), int(c_left), int(ty))
                if wy > 0 and int(wy) % 500 == 0:
                    label = f"{int(wy)}" if wy == int(wy) else f"{wy:.0f}"
                    p.drawText(int(c_left - 44), int(ty + 4), label)
            wy += 100.0

        # --- Origin "O" label ---
        font = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(font)
        p.setPen(QPen(axis_color, 1))
        p.drawText(int(c_left - 14), int(c_bottom + 16), "O")

        # --- Canvas dimension labels ---
        font_dim = QFont("Segoe UI", 8)
        p.setFont(font_dim)
        p.setPen(QPen(QColor(140, 140, 140)))
        mx_px = (c_left + c_right) / 2
        my_px = (c_top + c_bottom) / 2
        # Bottom: 3000mm
        p.drawText(int(mx_px - 22), int(c_bottom + 36), "3000 mm")
        # Left: 2000mm (vertical text)
        p.save()
        p.translate(int(c_left - 24), int(my_px + 30))
        p.rotate(-90)
        p.drawText(0, 0, "2000 mm")
        p.restore()

    def _draw_airfoil(self, p: QPainter):
        if self.airfoil_x is None or self.airfoil_y is None:
            return

        path = QPainterPath()
        x = self.airfoil_x
        y = self.airfoil_y

        # Scale to fit center of canvas (chord ~1000mm)
        scale = 1000.0
        cx, cy = self.world_w / 2, self.world_h / 2

        first = True
        for i in range(len(x)):
            px = (x[i] - 0.5) * scale + cx
            py = y[i] * scale + cy
            sx, sy = self._world_to_widget(px, py)
            if first:
                path.moveTo(sx, sy)
                first = False
            else:
                path.lineTo(sx, sy)
        path.closeSubpath()

        p.setBrush(QBrush(self._airfoil_fill))
        p.setPen(QPen(self._airfoil_stroke, 2))
        p.drawPath(path)

        # Label
        if self.airfoil_name:
            p.setPen(QPen(QColor(50, 50, 50), 1))
            font = QFont("Segoe UI", 10, QFont.Bold)
            p.setFont(font)
            lx, ly = self._world_to_widget(cx - 400, cy + 400)
            p.drawText(int(lx), int(ly), self.airfoil_name)

    def _draw_geometry_elements(self, p: QPainter):
        """Draw created points, lines, splines, and previews."""
        # Points
        p.setBrush(QBrush(self._point_color))
        p.setPen(Qt.NoPen)
        radius = max(3.0, self._point_radius)
        for wx, wy in self.points:
            px, py = self._world_to_widget(wx, wy)
            p.drawEllipse(QPointF(px, py), radius, radius)

        # Lines
        p.setPen(QPen(QColor(30, 30, 30), 1.5))
        for (x1, y1), (x2, y2) in self.lines:
            px1, py1 = self._world_to_widget(x1, y1)
            px2, py2 = self._world_to_widget(x2, y2)
            p.drawLine(int(px1), int(py1), int(px2), int(py2))

        # Completed splines
        p.setPen(QPen(QColor(31, 111, 235), 2))
        for curve in self.splines:
            for i in range(len(curve) - 1):
                px1, py1 = self._world_to_widget(*curve[i])
                px2, py2 = self._world_to_widget(*curve[i + 1])
                p.drawLine(int(px1), int(py1), int(px2), int(py2))

        # Pending spline control points + preview polyline
        if self._pending_points:
            # Preview polyline connecting control points
            p.setPen(QPen(QColor(31, 111, 235, 120), 1.2, Qt.DashLine))
            for i in range(len(self._pending_points) - 1):
                px1, py1 = self._world_to_widget(*self._pending_points[i])
                px2, py2 = self._world_to_widget(*self._pending_points[i + 1])
                p.drawLine(int(px1), int(py1), int(px2), int(py2))

            # Control point markers
            p.setBrush(QBrush(QColor(31, 111, 235)))
            p.setPen(Qt.NoPen)
            for wx, wy in self._pending_points:
                px, py = self._world_to_widget(wx, wy)
                p.drawEllipse(QPointF(px, py), radius + 1, radius + 1)

        # Line preview (from start to current mouse)
        if self._line_start is not None:
            p.setPen(QPen(self._line_preview, 1.5, Qt.DashLine))
            px1, py1 = self._world_to_widget(*self._line_start)
            cursor_pos = self.mapFromGlobal(self.cursor().pos())
            p.drawLine(int(px1), int(py1), cursor_pos.x(), cursor_pos.y())

    # ===== Public API =====

    def set_airfoil(self, x: np.ndarray, y: np.ndarray, name: str = ""):
        """Display an airfoil on the canvas."""
        self.airfoil_x = x.copy()
        self.airfoil_y = y.copy()
        self.airfoil_name = name
        if not self._initial_fit_done:
            self._fit_to_widget()
            self._initial_fit_done = True
        self.update()

    def clear_airfoil(self):
        self.airfoil_x = None
        self.airfoil_y = None
        self.airfoil_name = ""
        self.update()

    def clear_all(self):
        self.points.clear()
        self.lines.clear()
        self.splines.clear()
        self._pending_points = []
        self.clear_airfoil()
        self.update()

    def add_point(self, wx: float, wy: float):
        self.points.append((wx, wy))
        self.update()

    def add_line(self, x1: float, y1: float, x2: float, y2: float):
        self.lines.append(((x1, y1), (x2, y2)))
        self.update()

    def screen_to_world(self, px: float, py: float) -> tuple[float, float]:
        return self._widget_to_world(px, py)
