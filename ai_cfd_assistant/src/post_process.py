"""Post-processing panel — Cp contour, velocity, downforce after solve."""

from __future__ import annotations
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from .viz_widgets import MplCanvas, panel_method


class PostProcessPanel(QWidget):
    """Displays CFD results after solver runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = None
        self._airfoil = None
        self._alpha = 4.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("后处理 — 计算结果")
        header.setStyleSheet(
            "color: #c9d1d9; font-size: 13px; font-weight: 700; padding: 10px 14px; "
            "background: #161b22; border-bottom: 1px solid #30363d;"
        )
        layout.addWidget(header)

        # Summary row
        self.summary = QLabel("尚未求解 — 请点击菜单 [求解] → [开始求解]")
        self.summary.setStyleSheet(
            "color: #8b949e; font-size: 12px; padding: 10px 14px; background: #0d1117;"
        )
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        # Cp plot
        self.canvas = MplCanvas(figsize=(6, 3.5))
        self._draw_placeholder()
        layout.addWidget(self.canvas, stretch=1)

    def _draw_placeholder(self):
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        ax.set_facecolor('#0d1117')
        ax.text(0.5, 0.5, '求解后将在此显示\n压力系数分布 & 流线图',
                transform=ax.transAxes, ha='center', va='center',
                color='#484f58', fontsize=14)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color('#30363d')
        self.canvas.draw()

    def set_result(self, result, airfoil, alpha: float):
        """Update with solver results."""
        self._result = result
        self._airfoil = airfoil
        self._alpha = alpha
        self._update_display()

    def clear(self):
        self._result = None
        self._airfoil = None
        self.summary.setText("尚未求解 — 请点击菜单 [求解] → [开始求解]")
        self._draw_placeholder()

    def _update_display(self):
        if self._result is None or self._airfoil is None:
            self.clear()
            return

        r = self._result
        af = self._airfoil

        self.summary.setText(
            f"翼型: {af.naca_code}  |  攻角 α = {self._alpha:.1f}°  |  "
            f"Cl = {r.cl:.4f}  |  Cm = {r.cpm:.4f}"
        )

        self.canvas.fig.clear()

        # Top: Cp distribution
        ax1 = self.canvas.fig.add_subplot(211)
        ax1.set_facecolor('#0d1117')
        ax1.plot(r.x_panel, -r.cp, color='#58a6ff', linewidth=2)
        ax1.fill_between(r.x_panel, -r.cp, 0, color='#58a6ff', alpha=0.12)
        stag_idx = np.argmin(np.abs(r.u_e))
        ax1.plot(r.x_panel[stag_idx], -r.cp[stag_idx], 'o', color='#f85149', markersize=6)
        ax1.set_ylabel('-Cp', color='#8b949e', fontsize=8)
        ax1.set_title(f'压力系数分布 (α={self._alpha:.1f}°, Cl={r.cl:.4f})',
                      color='#c9d1d9', fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.15, color='#8b949e')
        ax1.tick_params(colors='#8b949e', labelsize=7)
        for spine in ax1.spines.values():
            spine.set_color('#30363d')

        # Bottom: Cp envelope vs airfoil
        ax2 = self.canvas.fig.add_subplot(212)
        ax2.set_facecolor('#0d1117')
        ax2.fill(af.x, af.y, color='#c9d1d9', alpha=0.6)
        # Color map on airfoil surface by Cp
        norm_cp = (r.cp - r.cp.min()) / (r.cp.max() - r.cp.min() + 1e-12)
        from matplotlib.cm import RdYlBu_r
        for i in range(len(r.x_panel) - 1):
            c = RdYlBu_r(norm_cp[i])
            ax2.plot(r.x_panel[i:i+2], r.y_panel[i:i+2], color=c, linewidth=3)
        ax2.set_xlabel('x/c', color='#8b949e', fontsize=8)
        ax2.set_ylabel('y/c', color='#8b949e', fontsize=8)
        ax2.set_title('翼面压力包络 (红=高压, 蓝=低压)', color='#c9d1d9', fontsize=9)
        ax2.set_aspect('equal')
        ax2.grid(True, alpha=0.15, color='#8b949e')
        ax2.tick_params(colors='#8b949e', labelsize=7)
        for spine in ax2.spines.values():
            spine.set_color('#30363d')

        self.canvas.fig.tight_layout(pad=2)
        self.canvas.draw()
