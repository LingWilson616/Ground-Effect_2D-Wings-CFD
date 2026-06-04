"""Structured O-mesh generator around a 2D airfoil.

Generates an O-type grid using transfinite interpolation (TFI).
Base cell size ~100mm, min near-wall ~0.1mm (normalized to chord).
"""

from __future__ import annotations
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout, QSpinBox, QPushButton
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QBrush


class MeshGenerator:
    """Generate structured O-mesh around airfoil."""

    def __init__(self, airfoil_x=None, airfoil_y=None, n_xi=60, n_eta=30, far_radius=8.0, wall_spacing=0.002):
        self.n_xi = n_xi          # points around airfoil (circumferential)
        self.n_eta = n_eta        # points from wall to farfield (radial)
        self.far_radius = far_radius       # outer boundary radius (chords)
        self.wall_spacing = wall_spacing   # first cell height (chords)
        self.growth = 1.15                 # growth factor

        self.airfoil_x = airfoil_x
        self.airfoil_y = airfoil_y

    def generate(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return (X, Y) mesh of shape (n_eta, n_xi) and (x_foil, y_foil)."""
        n_xi, n_eta = self.n_xi, self.n_eta

        # Airfoil surface points
        if self.airfoil_x is not None and self.airfoil_y is not None and len(self.airfoil_x) > 0:
            x_raw, y_raw = self.airfoil_x, self.airfoil_y
            # Resample to n_xi points
            indices = np.linspace(0, len(x_raw)-1, n_xi, dtype=int)
            x_foil = x_raw[indices]
            y_foil = y_raw[indices]
        else:
            theta = np.linspace(0, 2*np.pi, n_xi)
            x_foil = 0.5 + 0.05 * np.cos(theta)
            y_foil = 0.05 * np.sin(theta)

        # Outer boundary (circle)
        theta_o = np.linspace(0, 2*np.pi, n_xi)
        x_outer = 0.5 + self.far_radius * np.cos(theta_o)
        y_outer = self.far_radius * np.sin(theta_o)

        X = np.zeros((n_eta, n_xi))
        Y = np.zeros((n_eta, n_xi))

        # Exponential stretching in radial direction
        # s goes from 0 (wall) to 1 (farfield)
        s = np.zeros(n_eta)
        for i in range(1, n_eta):
            s[i] = s[i-1] + self.wall_spacing * (self.growth ** (i-1))
        # Normalize so s[-1] = 1
        s = s / s[-1]

        # TFI: X = (1-s)*x_foil + s*x_outer
        for j in range(n_eta):
            X[j, :] = (1 - s[j]) * x_foil + s[j] * x_outer
            Y[j, :] = (1 - s[j]) * y_foil + s[j] * y_outer

        return X, Y, x_foil, y_foil


class MeshCanvas(QWidget):
    """Displays generated O-mesh with grid info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #0d1117;")
        self.X = None
        self.Y = None
        self.x_foil = None
        self.y_foil = None
        self.info_text = ""
        self._bg = QColor(13, 17, 23)
        self._grid_color = QColor(72, 79, 88, 120)
        self._foil_color = QColor(31, 111, 235)

    def set_mesh(self, X, Y, x_foil, y_foil, info=""):
        self.X = X
        self.Y = Y
        self.x_foil = x_foil
        self.y_foil = y_foil
        self.info_text = info
        self.update()

    def clear(self):
        self.X = None
        self.Y = None
        self.info_text = ""
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bg)

        if self.X is None:
            p.setPen(QPen(QColor(72, 79, 88)))
            font = QFont("Segoe UI", 13)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignCenter, "点击\"生成网格\"生成O型结构网格")
            return

        w, h = self.width(), self.height()
        m = 30
        dw, dh = w - 2*m, h - 2*m

        # Compute bounds
        x_min, x_max = self.X.min(), self.X.max()
        y_min, y_max = self.Y.min(), self.Y.max()
        scale_x = dw / (x_max - x_min + 1e-12)
        scale_y = dh / (y_max - y_min + 1e-12)
        scale = min(scale_x, scale_y)
        cx = m + dw/2 - (x_min + x_max)/2 * scale
        cy = m + dh/2 + (y_min + y_max)/2 * scale  # flip y

        def to_px(x, y):
            return m + (x - x_min) * scale, h - m - (y - y_min) * scale

        # Draw mesh lines
        n_eta, n_xi = self.X.shape

        # xi-lines (circumferential) — every other line
        p.setPen(QPen(self._grid_color, 0.3))
        for j in range(0, n_eta, 2):
            path = QPainterPath()
            first = True
            for i in range(n_xi):
                px, py = to_px(self.X[j, i], self.Y[j, i])
                if first:
                    path.moveTo(px, py)
                    first = False
                else:
                    path.lineTo(px, py)
            p.drawPath(path)

        # eta-lines (radial) — every other line
        for i in range(0, n_xi, 4):
            path = QPainterPath()
            first = True
            for j in range(n_eta):
                px, py = to_px(self.X[j, i], self.Y[j, i])
                if first:
                    path.moveTo(px, py)
                    first = False
                else:
                    path.lineTo(px, py)
            p.drawPath(path)

        # Draw airfoil
        if self.x_foil is not None:
            p.setPen(QPen(self._foil_color, 2))
            p.setBrush(QBrush(QColor(31, 111, 235, 40)))
            foil_path = QPainterPath()
            first = True
            for i in range(len(self.x_foil)):
                px, py = to_px(self.x_foil[i], self.y_foil[i])
                if first:
                    foil_path.moveTo(px, py)
                    first = False
                else:
                    foil_path.lineTo(px, py)
            foil_path.closeSubpath()
            p.drawPath(foil_path)

        # Info text
        if self.info_text:
            p.setPen(QPen(QColor(201, 209, 217)))
            font = QFont("Segoe UI", 9)
            p.setFont(font)
            p.drawText(m, h - m + 16, self.info_text)


class MeshWorkspace(QWidget):
    """Mesh generation workspace with controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.airfoil_x = None
        self.airfoil_y = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("网格生成 — O型结构网格")
        header.setStyleSheet(
            "color: #c9d1d9; font-size: 13px; font-weight: 700; padding: 10px 14px; "
            "background: #161b22; border-bottom: 1px solid #30363d;"
        )
        layout.addWidget(header)

        # Controls row
        ctrl_row = QWidget()
        ctrl_row.setStyleSheet("background: #161b22; padding: 8px 12px; border-bottom: 1px solid #30363d;")
        ctrl_layout = QHBoxLayout(ctrl_row)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(12)

        # Mesh params
        from PySide6.QtWidgets import QSpinBox, QDoubleSpinBox
        self.n_xi = QSpinBox()
        self.n_xi.setRange(20, 200)
        self.n_xi.setValue(60)
        self.n_xi.setPrefix("周向: ")
        ctrl_layout.addWidget(self.n_xi)

        self.n_eta = QSpinBox()
        self.n_eta.setRange(10, 80)
        self.n_eta.setValue(30)
        self.n_eta.setPrefix("径向: ")
        ctrl_layout.addWidget(self.n_eta)

        self.wall_sp = QDoubleSpinBox()
        self.wall_sp.setRange(0.0001, 0.1)
        self.wall_sp.setValue(0.002)
        self.wall_sp.setDecimals(4)
        self.wall_sp.setSingleStep(0.001)
        self.wall_sp.setPrefix("首层高度: ")
        ctrl_layout.addWidget(self.wall_sp)

        gen_btn = QPushButton("生成网格")
        gen_btn.clicked.connect(self._generate)
        gen_btn.setStyleSheet(
            "QPushButton { background: #1f6feb; color: white; border: none; "
            "border-radius: 6px; padding: 6px 16px; font-weight: 600; }"
            "QPushButton:hover { background: #388bfd; }"
        )
        ctrl_layout.addWidget(gen_btn)

        ctrl_layout.addStretch()
        layout.addWidget(ctrl_row)

        self.canvas = MeshCanvas()
        layout.addWidget(self.canvas, stretch=1)

        # Status
        self.status = QLabel("尚未生成网格")
        self.status.setStyleSheet("color: #8b949e; font-size: 11px; padding: 8px 14px; background: #0d1117;")
        layout.addWidget(self.status)

    def set_airfoil(self, x, y):
        self.airfoil_x = x
        self.airfoil_y = y

    def _generate(self):
        if self.airfoil_x is None:
            self.status.setText("请先导入翼型")
            return

        gen = MeshGenerator(
            airfoil_x=self.airfoil_x,
            airfoil_y=self.airfoil_y,
            n_xi=self.n_xi.value(),
            n_eta=self.n_eta.value(),
            wall_spacing=self.wall_sp.value(),
        )
        X, Y, xf, yf = gen.generate()
        total_cells = (gen.n_xi - 1) * (gen.n_eta - 1)
        info = f"网格: {gen.n_xi}×{gen.n_eta} = {total_cells} 单元 | 首层高度: {self.wall_sp.value():.4f}c | 远场: {gen.far_radius}c"
        self.canvas.set_mesh(X, Y, xf, yf, info)
        self.status.setText(info)
