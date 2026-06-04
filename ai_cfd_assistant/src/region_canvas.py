"""Region configuration canvas — shows flow domain with boundary conditions."""

from __future__ import annotations
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QPainterPath, QBrush,
)


class RegionCanvas(QWidget):
    """Visual display of the CFD domain with BC labels.

    Default: left=velocity inlet, right=pressure outlet, top/bottom=walls.
    Shows imported airfoil inside the domain.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #161b22;")

        self.world_w = 3000.0
        self.world_h = 2000.0
        self._margin = 60

        self.airfoil_x = None
        self.airfoil_y = None
        self.airfoil_name = ""

        # Colors
        self._bg = QColor(22, 27, 34)
        self._domain_fill = QColor(13, 17, 23)
        self._domain_stroke = QColor(72, 79, 88, 200)
        self._airfoil_fill = QColor(31, 111, 235, 50)
        self._airfoil_stroke = QColor(31, 111, 235)
        self._inlet_color = QColor(88, 166, 255)       # blue
        self._outlet_color = QColor(63, 185, 80)         # green
        self._wall_color = QColor(210, 168, 255)         # purple
        self._text_color = QColor(201, 209, 217)
        self._arrow_color = QColor(241, 224, 90)         # yellow

    def set_airfoil(self, x: np.ndarray, y: np.ndarray, name: str = ""):
        self.airfoil_x = x.copy()
        self.airfoil_y = y.copy()
        self.airfoil_name = name
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        m = self._margin

        # Background
        p.fillRect(self.rect(), self._bg)

        # Domain rectangle (flow field)
        domain_rect_x = m
        domain_rect_y = m
        domain_rect_w = w - 2 * m
        domain_rect_h = h - 2 * m

        p.setBrush(QBrush(self._domain_fill))
        p.setPen(QPen(self._domain_stroke, 2))
        p.drawRoundedRect(domain_rect_x, domain_rect_y, domain_rect_w, domain_rect_h, 8, 8)

        # Scale info
        font_small = QFont("Segoe UI", 8)
        p.setFont(font_small)
        p.setPen(QPen(QColor(139, 148, 158)))
        p.drawText(domain_rect_x + 4, domain_rect_y + domain_rect_h + 16, "3000 mm × 2000 mm")

        # Draw airfoil inside domain
        if self.airfoil_x is not None and self.airfoil_y is not None:
            self._draw_airfoil_in_domain(p, domain_rect_x, domain_rect_y,
                                         domain_rect_w, domain_rect_h)

        # Boundary condition labels
        self._draw_bc_labels(p, domain_rect_x, domain_rect_y, domain_rect_w, domain_rect_h)

    def _draw_airfoil_in_domain(self, p, dx, dy, dw, dh):
        """Draw airfoil centered at domain center, scaled to ~40% of domain width."""
        x, y = self.airfoil_x, self.airfoil_y
        # Scale: chord occupies ~40% of domain width
        scale = dw * 0.4
        cx = dx + dw / 2
        cy = dy + dh / 2
        x_scaled = (x - 0.5) * scale + cx
        y_scaled = y * scale + cy

        path = QPainterPath()
        first = True
        for xi, yi in zip(x_scaled, y_scaled):
            if first:
                path.moveTo(xi, yi)
                first = False
            else:
                path.lineTo(xi, yi)
        path.closeSubpath()

        p.setBrush(QBrush(self._airfoil_fill))
        p.setPen(QPen(self._airfoil_stroke, 2))
        p.drawPath(path)

        # Label
        if self.airfoil_name:
            p.setPen(QPen(self._text_color))
            font = QFont("Segoe UI", 9, QFont.Bold)
            p.setFont(font)
            fm = p.fontMetrics()
            text_w = fm.horizontalAdvance(self.airfoil_name)
            p.drawText(int(cx - text_w / 2), int(cy + scale * 0.3 + 20), self.airfoil_name)

    def _draw_bc_labels(self, p, dx, dy, dw, dh):
        """Draw boundary condition indicators on each edge."""
        mx = dx + dw / 2
        my = dy + dh / 2

        font = QFont("Segoe UI", 10, QFont.Bold)
        p.setFont(font)

        # Left — Velocity Inlet (blue)
        p.setPen(QPen(self._inlet_color, 3))
        p.drawLine(dx, dy, dx, dy + dh)
        # Arrows into domain
        for frac in [0.2, 0.35, 0.5, 0.65, 0.8]:
            ay = dy + dh * frac
            p.drawLine(dx, int(ay), dx + 25, int(ay))
            p.drawLine(dx + 25, int(ay), dx + 18, int(ay - 6))
            p.drawLine(dx + 25, int(ay), dx + 18, int(ay + 6))
        p.setPen(QPen(self._inlet_color))
        p.save()
        p.translate(int(dx - 30), int(my))
        p.rotate(-90)
        p.drawText(-40, 0, "速度进口 (Velocity Inlet)")
        p.restore()

        # Right — Pressure Outlet (green)
        p.setPen(QPen(self._outlet_color, 3))
        p.drawLine(dx + dw, dy, dx + dw, dy + dh)
        for frac in [0.2, 0.35, 0.5, 0.65, 0.8]:
            ay = dy + dh * frac
            p.drawLine(dx + dw, int(ay), dx + dw - 25, int(ay))
        p.setPen(QPen(self._outlet_color))
        p.drawText(int(dx + dw + 6), int(my - 10), "压力出口")
        p.drawText(int(dx + dw + 6), int(my + 10), "(Pressure Outlet)")

        # Top — Wall (purple)
        p.setPen(QPen(self._wall_color, 3))
        p.drawLine(dx, dy, dx + dw, dy)
        # Hatch marks
        for frac in range(5, 95, 10):
            hx = dx + dw * frac / 100.0
            p.drawLine(int(hx), dy, int(hx + 8), dy + 12)
        p.setPen(QPen(self._wall_color))
        p.drawText(int(mx - 30), int(dy - 10), "壁面 (Wall)")

        # Bottom — Wall / Ground (purple)
        p.setPen(QPen(self._wall_color, 3))
        p.drawLine(dx, dy + dh, dx + dw, dy + dh)
        for frac in range(5, 95, 10):
            hx = dx + dw * frac / 100.0
            p.drawLine(int(hx), dy + dh, int(hx + 8), dy + dh - 12)
        p.setPen(QPen(self._wall_color))
        p.drawText(int(mx - 30), int(dy + dh + 18), "壁面 (Wall) / 地面")

        # Corner labels
        font_sm = QFont("Segoe UI", 7)
        p.setFont(font_sm)
        p.setPen(QPen(QColor(139, 148, 158)))
        p.drawText(dx + 4, dy + 14, "(0, 2000)")
        p.drawText(dx + 4, dy + dh - 4, "(0, 0)")
        p.drawText(dx + dw - 40, dy + dh - 4, "(3000, 0)")

        # Fluid properties box (top-right corner)
        self._draw_fluid_props(p, dx, dy, dw)

    def _draw_fluid_props(self, p, dx, dy, dw):
        """Draw fluid properties panel in top-right of domain."""
        box_x = dx + dw - 195
        box_y = dy + 14
        box_w = 180
        box_h = 130

        p.setBrush(QBrush(QColor(22, 27, 34, 230)))
        p.setPen(QPen(QColor(48, 54, 61), 1))
        p.drawRoundedRect(int(box_x), int(box_y), int(box_w), int(box_h), 6, 6)

        font = QFont("Segoe UI", 8)
        p.setFont(font)
        p.setPen(QPen(QColor(88, 166, 255)))
        p.drawText(int(box_x + 8), int(box_y + 16), "流体参数")

        props = [
            ("类型", "气体 (Air)"),
            ("状态", "分离流"),
            ("密度", "恒密度"),
            ("流动", "定常 (Steady)"),
            ("湍流模型", "k-ε (Standard)"),
        ]
        p.setPen(QPen(QColor(201, 209, 217)))
        for i, (key, val) in enumerate(props):
            py = box_y + 34 + i * 18
            p.drawText(int(box_x + 8), int(py), f"{key}:")
            p.setPen(QPen(QColor(139, 148, 158)))
            p.drawText(int(box_x + 70), int(py), val)
            p.setPen(QPen(QColor(201, 209, 217)))
