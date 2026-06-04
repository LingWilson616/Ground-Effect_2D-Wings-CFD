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

        # Line drawing state
        self._line_start = None  # waiting for second point
        self._pending_points = []  # for spline

        # Tool system
        self._current_tool = GeoTool.SELECT

        # Geometry elements
        self.points: list[tuple[float, float]] = []
        self.lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
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
            GeoTool.SELECT: "选择/平移 — 左键拖动平移，右键创建点",
            GeoTool.POINT: "点工具 — 右键点击画布创建点",
            GeoTool.LINE: "直线工具 — 右键点击两点创建直线 (Esc 取消)",
            GeoTool.SPLINE: "样条线 — 右键点击多个点，双击完成",
            GeoTool.CREATE: "创建 — 右键点击创建几何元素",
            GeoTool.DELETE: "删除 — 点击删除最近的几何元素",
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
        wx, wy = self._widget_to_world(event.position().x(), event.position().y())
        in_bounds = 0 <= wx <= self.world_w and 0 <= wy <= self.world_h

        if event.button() == Qt.LeftButton:
            # Left button always pans (or moves in MOVE tool)
            self._panning = True
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            self._pan_start_offset_x = self._offset_x
            self._pan_start_offset_y = self._offset_y
            self.setCursor(Qt.ClosedHandCursor)

        elif event.button() == Qt.RightButton:
            if not in_bounds:
                return
            tool = self._current_tool
            if tool == GeoTool.SELECT or tool == GeoTool.POINT or tool == GeoTool.CREATE:
                self.points.append((wx, wy))
                self.point_created.emit(wx, wy)
            elif tool == GeoTool.LINE:
                if self._line_start is None:
                    self._line_start = (wx, wy)
                    self.status_changed.emit(f"直线起点: ({wx:.1f}, {wy:.1f}) — 右键点击终点")
                else:
                    self.lines.append((self._line_start, (wx, wy)))
                    self.status_changed.emit(f"直线: ({self._line_start[0]:.1f},{self._line_start[1]:.1f}) → ({wx:.1f},{wy:.1f})")
                    self._line_start = None
            elif tool == GeoTool.SPLINE:
                self._pending_points.append((wx, wy))
                self.status_changed.emit(f"样条线点 {len(self._pending_points)}: ({wx:.1f}, {wy:.1f}) — 右键继续，双击完成")
            elif tool == GeoTool.DELETE:
                if self.points:
                    removed = self.points.pop()
                    self.status_changed.emit(f"已删除点: ({removed[0]:.1f}, {removed[1]:.1f})")
                elif self.lines:
                    removed = self.lines.pop()
                    self.status_changed.emit("已删除最近一条直线")
            self.update()

        elif event.button() == Qt.MiddleButton:
            self._fit_to_widget()
            self.status_changed.emit("视图已重置")

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.RightButton and self._current_tool == GeoTool.SPLINE:
            if len(self._pending_points) >= 2:
                self.status_changed.emit(f"样条线完成: {len(self._pending_points)} 个控制点")
                self._pending_points = []
            else:
                self.status_changed.emit("样条线至少需要2个点")
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            dx = event.position().x() - self._pan_start_x
            dy = event.position().y() - self._pan_start_y
            self._offset_x = self._pan_start_offset_x + dx
            self._offset_y = self._pan_start_offset_y - dy
            self._clamp_view()
            self.update()
        wx, wy = self._widget_to_world(event.position().x(), event.position().y())
        self.mouse_moved.emit(wx, wy)
        if self._line_start is not None:
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)

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
        p.drawText(self.width() - 160, self.height() - 12, f"工具: {name} | 右键操作")

    def _draw_background(self, p: QPainter):
        p.fillRect(self.rect(), self._bg_color)

    def _draw_grid(self, p: QPainter):
        """Draw adaptive grid — show finer grid when zoomed in."""
        w, h = self.width(), self.height()

        # Choose grid spacing based on zoom
        px_per_100mm = 100 * self._scale
        if px_per_100mm > 80:
            step = self._grid_minor_mm  # 10mm
            pen = QPen(self._grid_minor, 0.3)
        elif px_per_100mm > 30:
            step = self._grid_minor_mm
            pen = QPen(self._grid_minor, 0.3)
        else:
            step = self._grid_base_mm
            pen = QPen(self._grid_major, 0.5)

        p.setPen(pen)

        # Vertical lines
        x0 = 0
        while True:
            px, _ = self._world_to_widget(x0, 0)
            if px > w:
                break
            if px >= 0:
                p.drawLine(int(px), 0, int(px), h)
            x0 += step
        x0 = -step
        while True:
            px, _ = self._world_to_widget(x0, 0)
            if px < 0:
                break
            if px <= w:
                p.drawLine(int(px), 0, int(px), h)
            x0 -= step

        # Horizontal lines
        y0 = 0
        while True:
            _, py = self._world_to_widget(0, y0)
            if py < 0:
                break
            if py <= h:
                p.drawLine(0, int(py), w, int(py))
            y0 += step
        y0 = -step
        while True:
            _, py = self._world_to_widget(0, y0)
            if py > h:
                break
            if py >= 0:
                p.drawLine(0, int(py), w, int(py))
            y0 -= step

    def _draw_axes(self, p: QPainter):
        """Draw XY axes spanning visible area with tick marks."""
        w, h = self.width(), self.height()
        wx_min, wy_min = self._widget_to_world(0, h)
        wx_max, wy_max = self._widget_to_world(w, 0)

        # X axis at y=0 (if visible)
        if wy_min <= 0 <= wy_max:
            px_start, py_y0 = self._world_to_widget(max(0, wx_min), 0)
            px_end, _ = self._world_to_widget(min(self.world_w, wx_max), 0)
            p.setPen(QPen(self._axis_color, 1.5))
            p.drawLine(int(px_start), int(py_y0), int(px_end), int(py_y0))
            p.drawLine(int(px_end), int(py_y0), int(px_end - 10), int(py_y0 - 4))
            p.drawLine(int(px_end), int(py_y0), int(px_end - 10), int(py_y0 + 4))
            font = QFont("Segoe UI", 11, QFont.Bold)
            p.setFont(font)
            p.setPen(QPen(self._axis_color, 1))
            p.drawText(int(px_end + 2), int(py_y0 + 4), "X")
            # Tick marks every 100mm
            x_tick = 0
            while x_tick <= self.world_w:
                if wx_min <= x_tick <= wx_max:
                    tx, ty = self._world_to_widget(x_tick, 0)
                    p.drawLine(int(tx), int(ty - 6), int(tx), int(ty + 6))
                    if x_tick % 500 == 0 and x_tick > 0:
                        font2 = QFont("Segoe UI", 7)
                        p.setFont(font2)
                        p.drawText(int(tx - 20), int(ty + 16), f"{x_tick}")
                x_tick += 100

        # Y axis at x=0 (if visible)
        if wx_min <= 0 <= wx_max:
            px_x0, py_start = self._world_to_widget(0, max(0, wy_min))
            _, py_end = self._world_to_widget(0, min(self.world_h, wy_max))
            p.setPen(QPen(self._axis_color, 1.5))
            p.drawLine(int(px_x0), int(py_start), int(px_x0), int(py_end))
            p.drawLine(int(px_x0), int(py_end), int(px_x0 - 4), int(py_end + 10))
            p.drawLine(int(px_x0), int(py_end), int(px_x0 + 4), int(py_end + 10))
            font = QFont("Segoe UI", 11, QFont.Bold)
            p.setFont(font)
            p.setPen(QPen(self._axis_color, 1))
            p.drawText(int(px_x0 + 6), int(py_end + 14), "Y")
            # Tick marks every 100mm
            y_tick = 0
            while y_tick <= self.world_h:
                if wy_min <= y_tick <= wy_max:
                    tx, ty = self._world_to_widget(0, y_tick)
                    p.drawLine(int(tx - 6), int(ty), int(tx + 6), int(ty))
                    if y_tick % 500 == 0 and y_tick > 0:
                        font2 = QFont("Segoe UI", 7)
                        p.setFont(font2)
                        p.drawText(int(tx - 44), int(ty + 4), f"{y_tick}")
                y_tick += 100

        # Origin label
        ox, oy = self._world_to_widget(0, 0)
        font = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(font)
        p.setPen(QPen(self._axis_color, 1))
        p.drawText(int(ox - 14), int(oy + 15), "O")

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
        """Draw created points, lines, and previews."""
        # Points
        p.setBrush(QBrush(self._point_color))
        p.setPen(Qt.NoPen)
        radius = max(3.0, self._point_radius)
        for wx, wy in self.points:
            px, py = self._world_to_widget(wx, wy)
            p.drawEllipse(QPointF(px, py), radius, radius)

        # Pending spline points
        if self._pending_points:
            p.setBrush(QBrush(QColor(31, 111, 235)))
            p.setPen(Qt.NoPen)
            for wx, wy in self._pending_points:
                px, py = self._world_to_widget(wx, wy)
                p.drawEllipse(QPointF(px, py), radius, radius)

        # Lines
        p.setPen(QPen(QColor(30, 30, 30), 1.5))
        for (x1, y1), (x2, y2) in self.lines:
            px1, py1 = self._world_to_widget(x1, y1)
            px2, py2 = self._world_to_widget(x2, y2)
            p.drawLine(int(px1), int(py1), int(px2), int(py2))

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
