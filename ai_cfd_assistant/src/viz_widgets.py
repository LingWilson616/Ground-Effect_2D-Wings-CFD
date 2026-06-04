"""CFD Visualization panels embedded in Qt via matplotlib."""

from __future__ import annotations
import numpy as np
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

# Configure CJK font for matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QComboBox, QDoubleSpinBox, QPushButton,
    QGroupBox, QFormLayout, QSpinBox, QSizePolicy, QFrame,
)

from .cfd_core import naca4, naca5, panel_method, compute_streamlines


class MplCanvas(FigureCanvasQTAgg):
    """Base matplotlib canvas with dark theme."""
    def __init__(self, figsize=(5, 4)):
        self.fig = Figure(figsize=figsize, dpi=100, facecolor='#0d1117')
        super().__init__(self.fig)
        self.setStyleSheet("background-color: #0d1117; border: none;")


class AirfoilPanel(QWidget):
    """Interactive airfoil shape visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_x = None
        self._custom_y = None
        self._custom_name = ""
        self._setup_ui()
        self._update_plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Controls
        controls = QGroupBox("翼型参数")
        controls.setStyleSheet(self._group_style())
        form = QFormLayout(controls)
        form.setSpacing(6)

        self.naca_series = QComboBox()
        self.naca_series.addItems(["4-digit", "5-digit"])
        self.naca_series.currentTextChanged.connect(self._update_plot)

        self.naca_code = QComboBox()
        self.naca_code.setEditable(True)
        self.naca_code.addItems(["2412", "4412", "0012", "2410", "6412", "23012", "0015", "4415"])
        self.naca_code.setCurrentText("2412")
        self.naca_code.currentTextChanged.connect(self._update_plot)
        self.naca_code.lineEdit().returnPressed.connect(self._update_plot)

        self.n_points = QSpinBox()
        self.n_points.setRange(40, 400)
        self.n_points.setValue(160)
        self.n_points.setSingleStep(20)
        self.n_points.valueChanged.connect(self._update_plot)

        form.addRow("系列:", self.naca_series)
        form.addRow("翼型代码:", self.naca_code)
        form.addRow("离散点数:", self.n_points)
        layout.addWidget(controls)

        # Canvas
        self.canvas = MplCanvas(figsize=(4.5, 3.5))
        layout.addWidget(self.canvas, stretch=1)

    def _group_style(self):
        return """
            QGroupBox { color: #c9d1d9; font-weight: 600; border: 1px solid #30363d;
                border-radius: 8px; margin-top: 12px; padding: 14px 10px 10px 10px; }
            QGroupBox::title { subcontrol-origin: margin; padding: 0 6px; color: #58a6ff;
                font-size: 11px; text-transform: uppercase; }
        """

    def get_airfoil(self):
        code = self.naca_code.currentText().strip()
        if self.naca_series.currentText() == "4-digit" and len(code) == 4 and code.isdigit():
            return naca4(code, self.n_points.value())
        elif len(code) == 5 and code.isdigit():
            return naca5(code, self.n_points.value())
        elif len(code) == 4 and code.isdigit():
            return naca4(code, self.n_points.value())
        return naca4("2412", self.n_points.value())

    def set_custom_airfoil(self, x: np.ndarray, y: np.ndarray, name: str = ""):
        """Set a custom airfoil from imported DAT data."""
        self._custom_x = x
        self._custom_y = y
        self._custom_name = name
        self.naca_code.setEnabled(False)
        self.naca_series.setEnabled(False)
        self._update_plot()

    def _update_plot(self):
        is_custom = self._custom_x is not None
        if is_custom:
            x, y = self._custom_x, self._custom_y
            name = self._custom_name
        else:
            try:
                af = self.get_airfoil()
            except Exception:
                return
            xu, yu, xl, yl = af.xu, af.yu, af.xl, af.yl
            camber = af.camber
            name = f"NACA {af.naca_code}"

        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        ax.set_facecolor('#0d1117')

        if is_custom:
            n_half = len(x) // 2
            ax.plot(x[:n_half], y[:n_half], color='#58a6ff', linewidth=2, label='上表面')
            ax.plot(x[n_half:], y[n_half:], color='#a5d6ff', linewidth=2, label='下表面')
            ax.fill(np.concatenate([x[:n_half], x[n_half:][::-1]]),
                    np.concatenate([y[:n_half], y[n_half:][::-1]]),
                    color='#58a6ff', alpha=0.15)
        else:
            ax.plot(af.xu, af.yu, color='#58a6ff', linewidth=2, label='上表面')
            ax.plot(af.xl, af.yl, color='#a5d6ff', linewidth=2, label='下表面')
            ax.plot(af.xu, af.camber, '--', color='#8b949e', linewidth=1, alpha=0.6, label='中弧线')
            ax.fill(af.x, af.y, color='#58a6ff', alpha=0.15)

        ax.set_xlabel('x/c', color='#8b949e', fontsize=9)
        ax.set_ylabel('y/c', color='#8b949e', fontsize=9)
        ax.set_title(f'{name} 翼型', color='#c9d1d9', fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d',
                  labelcolor='#c9d1d9', fontsize=8)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.15, color='#8b949e')
        ax.tick_params(colors='#8b949e', labelsize=8)
        ax.set_xlim(-0.05, 1.05)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

        self.canvas.fig.tight_layout(pad=1.5)
        self.canvas.draw()


class PressurePanel(QWidget):
    """Pressure coefficient distribution visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_x = None
        self._custom_y = None
        self._custom_name = ""
        self._setup_ui()
        self._update_plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        controls = QGroupBox("来流参数")
        controls.setStyleSheet(self._group_style())
        form = QFormLayout(controls)
        form.setSpacing(6)

        self.alpha = QDoubleSpinBox()
        self.alpha.setRange(-20, 20)
        self.alpha.setValue(4.0)
        self.alpha.setSuffix("°")
        self.alpha.setSingleStep(0.5)
        self.alpha.valueChanged.connect(self._update_plot)

        self.n_panels = QSpinBox()
        self.n_panels.setRange(20, 200)
        self.n_panels.setValue(80)
        self.n_panels.setSingleStep(10)
        self.n_panels.valueChanged.connect(self._update_plot)

        form.addRow("攻角 (α):", self.alpha)
        form.addRow("面元数:", self.n_panels)
        layout.addWidget(controls)

        # Results
        self.result_label = QLabel("Cl: -- | Cm: --")
        self.result_label.setStyleSheet("color:#58a6ff;font-weight:600;font-size:13px;padding:4px 0;")
        self.result_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.result_label)

        self.canvas = MplCanvas(figsize=(4.5, 3.5))
        layout.addWidget(self.canvas, stretch=1)

    def _group_style(self):
        return """
            QGroupBox { color: #c9d1d9; font-weight: 600; border: 1px solid #30363d;
                border-radius: 8px; margin-top: 12px; padding: 14px 10px 10px 10px; }
            QGroupBox::title { subcontrol-origin: margin; padding: 0 6px; color: #d2a8ff;
                font-size: 11px; text-transform: uppercase; }
        """

    def set_custom_airfoil(self, x: np.ndarray, y: np.ndarray, name: str = ""):
        self._custom_x = x
        self._custom_y = y
        self._custom_name = name

    def get_airfoil(self):
        from .cfd_core import AirfoilResult
        if self._custom_x is not None:
            x, y = self._custom_x, self._custom_y
            n = len(x) // 2
            return AirfoilResult(
                x=x, y=y, xu=x[:n], yu=y[:n],
                xl=x[n:], yl=y[n:], camber=np.zeros(n),
                naca_code=self._custom_name,
            )
        return naca4("2412", 160)

    def _update_plot(self):
        try:
            af = self.get_airfoil()
            result = panel_method(af, self.alpha.value(), self.n_panels.value())
        except Exception:
            return

        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        ax.set_facecolor('#0d1117')

        # Inverted Cp (negative up in aerodynamics convention)
        ax.plot(result.x_panel, -result.cp, color='#58a6ff', linewidth=2)
        ax.fill_between(result.x_panel, -result.cp, 0, color='#58a6ff', alpha=0.12)

        # Mark stagnation point
        stag_x, stag_y = result.stagnation_pt
        # Find corresponding Cp
        dists = np.sqrt((result.x_panel - stag_x) ** 2 + (result.y_panel - stag_y) ** 2)
        stag_idx = np.argmin(dists)
        ax.plot(result.x_panel[stag_idx], -result.cp[stag_idx], 'o',
                color='#f85149', markersize=8, label='驻点')

        ax.set_xlabel('x/c', color='#8b949e', fontsize=9)
        ax.set_ylabel('-Cp', color='#8b949e', fontsize=9)
        title = f'压力系数分布 (α={self.alpha.value():.1f}°)'
        ax.set_title(title, color='#c9d1d9', fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d',
                  labelcolor='#c9d1d9', fontsize=8)
        ax.grid(True, alpha=0.15, color='#8b949e')
        ax.tick_params(colors='#8b949e', labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

        self.canvas.fig.tight_layout(pad=1.5)
        self.canvas.draw()

        self.result_label.setText(f"Cl = {result.cl:.4f}  |  Cm = {result.cpm:.4f}")


class StreamlinePanel(QWidget):
    """Streamline / velocity field visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_x = None
        self._custom_y = None
        self._custom_name = ""
        self._setup_ui()
        self._update_plot()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        controls = QGroupBox("流场参数")
        controls.setStyleSheet(self._group_style())
        form = QFormLayout(controls)
        form.setSpacing(6)

        self.alpha_stream = QDoubleSpinBox()
        self.alpha_stream.setRange(-20, 20)
        self.alpha_stream.setValue(4.0)
        self.alpha_stream.setSuffix("°")
        self.alpha_stream.setSingleStep(0.5)
        self.alpha_stream.valueChanged.connect(self._update_plot)

        self.n_stream = QSpinBox()
        self.n_stream.setRange(5, 50)
        self.n_stream.setValue(20)
        self.n_stream.setSingleStep(5)
        self.n_stream.valueChanged.connect(self._update_plot)

        form.addRow("攻角 (α):", self.alpha_stream)
        form.addRow("流线数:", self.n_stream)
        layout.addWidget(controls)

        self.canvas = MplCanvas(figsize=(4.5, 3.5))
        layout.addWidget(self.canvas, stretch=1)

    def _group_style(self):
        return """
            QGroupBox { color: #c9d1d9; font-weight: 600; border: 1px solid #30363d;
                border-radius: 8px; margin-top: 12px; padding: 14px 10px 10px 10px; }
            QGroupBox::title { subcontrol-origin: margin; padding: 0 6px; color: #3fb950;
                font-size: 11px; text-transform: uppercase; }
        """

    def set_custom_airfoil(self, x: np.ndarray, y: np.ndarray, name: str = ""):
        self._custom_x = x
        self._custom_y = y
        self._custom_name = name

    def _update_plot(self):
        try:
            from .cfd_core import AirfoilResult
            if self._custom_x is not None:
                x_c, y_c = self._custom_x, self._custom_y
                n = len(x_c) // 2
                af = AirfoilResult(
                    x=x_c, y=y_c, xu=x_c[:n], yu=y_c[:n],
                    xl=x_c[n:], yl=y_c[n:], camber=np.zeros(n),
                    naca_code=self._custom_name,
                )
            else:
                af = naca4("2412", 160)
            result = panel_method(af, self.alpha_stream.value(), 80)
            streamlines = compute_streamlines(af, result, self.alpha_stream.value(),
                                              n_streamlines=self.n_stream.value())
        except Exception:
            return

        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        ax.set_facecolor('#0d1117')

        # Plot airfoil
        ax.fill(af.x, af.y, color='#c9d1d9', alpha=0.9, zorder=5)

        # Plot streamlines
        colors = matplotlib.cm.viridis(np.linspace(0.2, 0.9, len(streamlines)))
        for i, sl in enumerate(streamlines):
            if len(sl) > 1:
                ax.plot(sl[:, 0], sl[:, 1], color=colors[i], linewidth=0.8, alpha=0.7)

        # Freestream arrow
        alpha_rad = np.radians(self.alpha_stream.value())
        ax.arrow(-0.3, 0, 0.15 * np.cos(alpha_rad), 0.15 * np.sin(alpha_rad),
                 head_width=0.03, head_length=0.05, fc='#58a6ff', ec='#58a6ff',
                 alpha=0.8, label='V∞')

        ax.set_xlabel('x/c', color='#8b949e', fontsize=9)
        ax.set_ylabel('y/c', color='#8b949e', fontsize=9)
        title = f'流线图 (α={self.alpha_stream.value():.1f}°)'
        ax.set_title(title, color='#c9d1d9', fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', facecolor='#161b22', edgecolor='#30363d',
                  labelcolor='#c9d1d9', fontsize=8)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.15, color='#8b949e')
        ax.tick_params(colors='#8b949e', labelsize=8)
        ax.set_xlim(-0.5, 2.0)
        ax.set_ylim(-0.8, 0.8)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

        self.canvas.fig.tight_layout(pad=1.5)
        self.canvas.draw()


class VizPanel(QWidget):
    """Combined visualization panel with tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("CFD 可视化")
        header.setStyleSheet("""
            color: #c9d1d9; font-size: 14px; font-weight: 700;
            padding: 10px 12px; background: #161b22; border-bottom: 1px solid #30363d;
        """)
        layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.airfoil_panel = AirfoilPanel()
        self.pressure_panel = PressurePanel()
        self.streamline_panel = StreamlinePanel()

        self.tabs.addTab(self.airfoil_panel, "🪽 翼型")
        self.tabs.addTab(self.pressure_panel, "📊 压力系数")
        self.tabs.addTab(self.streamline_panel, "🌊 流线")

        layout.addWidget(self.tabs, stretch=1)

    def set_airfoil(self, naca_code: str):
        """Update airfoil across all panels."""
        self.airfoil_panel.naca_code.setCurrentText(naca_code)
        self.airfoil_panel._update_plot()
        self.pressure_panel._update_plot()
        self.streamline_panel._update_plot()
