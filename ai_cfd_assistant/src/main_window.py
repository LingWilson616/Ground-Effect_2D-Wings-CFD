"""Main window — follows prompt.txt GUI spec: menu bar, toolbar, tree view, workspace, status bar, property panel."""

from __future__ import annotations
import os
import json
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar,
    QTreeWidget, QTreeWidgetItem, QSplitter, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QFileDialog,
    QStackedWidget, QSizePolicy, QFrame, QDockWidget, QHeaderView,
)
from .chat_widget import ChatWidget
from .viz_widgets import VizPanel
from .geometry_canvas import InteractiveGeometryCanvas
from .region_canvas import RegionCanvas
from .ai_client import AIClient
from .theme import QSS


MAIN_STYLE = """
QMainWindow {
    background-color: #0d1117;
}
QMainWindow::separator {
    width: 1px;
    background: #30363d;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ai_client = AIClient()
        self.current_airfoil_data = None  # imported/current airfoil points [(x,y), ...]
        self.current_airfoil_name = "NACA 2412"
        self.current_result = None  # last PanelMethodResult
        self.current_alpha = 4.0
        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_central()

    def _setup_window(self):
        self.setWindowTitle("近地翼片 2D-CFD 仿真")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        self.setStyleSheet(MAIN_STYLE + QSS)

    def _setup_menu(self):
        menubar = self.menuBar()

        # --- 文件 menu ---
        file_menu = menubar.addMenu("文件(&F)")

        new_action = QAction("新建项目", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._on_new)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        import_action = QAction("导入翼型 (.dat)", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import_dat)
        file_menu.addAction(import_action)

        export_action = QAction("导出结果", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        save_action = QAction("保存项目", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # --- 求解 menu ---
        solve_menu = menubar.addMenu("求解(&S)")

        solve_action = QAction("开始求解", self)
        solve_action.setShortcut(QKeySequence("F5"))
        solve_action.triggered.connect(self._on_solve)
        solve_menu.addAction(solve_action)

        clear_action = QAction("清除求解", self)
        clear_action.setShortcut(QKeySequence("F6"))
        clear_action.triggered.connect(self._on_clear_solve)
        solve_menu.addAction(clear_action)

        # --- 帮助 menu ---
        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        from .geometry_canvas import GeoTool
        self.toolbar = QToolBar("几何工具栏")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self._geo_tool_actions = {}
        self._geo_tool_group = None  # QActionGroup for exclusive selection

        def make_action(text, tool):
            a = self.toolbar.addAction(text)
            a.setCheckable(True)
            a.triggered.connect(lambda: self._set_geo_tool(tool))
            self._geo_tool_actions[tool] = a
            return a

        make_action("📌 点", GeoTool.POINT)
        make_action("📏 直线", GeoTool.LINE)
        make_action("〰️ 样条线", GeoTool.SPLINE)
        self.toolbar.addSeparator()
        make_action("🔍 选择", GeoTool.SELECT)
        make_action("↔ 移动", GeoTool.MOVE)
        make_action("🗑 删除", GeoTool.DELETE)
        self.toolbar.addSeparator()
        cons1 = self.toolbar.addAction("🔗 重合约束")
        cons1.setCheckable(True)
        cons2 = self.toolbar.addAction("🔒 固联约束")
        cons2.setCheckable(True)
        cons1.triggered.connect(lambda: self._set_status("约束: 重合 (待实现)"))
        cons2.triggered.connect(lambda: self._set_status("约束: 固联 (待实现)"))

        self.toolbar.hide()

    def _set_geo_tool(self, tool):
        if hasattr(self, 'geo_canvas'):
            self.geo_canvas.set_tool(tool)
        # Uncheck all tool actions, then check the active one
        for t, a in self._geo_tool_actions.items():
            a.setChecked(t == tool)

    def _setup_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left sidebar: Tree view ---
        left_widget = QWidget()
        left_widget.setFixedWidth(240)
        left_widget.setStyleSheet("background-color: #0d1117; border-right: 1px solid #30363d;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        tree_header = QLabel("项目浏览器")
        tree_header.setStyleSheet(
            "color: #c9d1d9; font-size: 12px; font-weight: 700; padding: 10px 12px; "
            "background: #161b22; border-bottom: 1px solid #30363d;"
        )
        left_layout.addWidget(tree_header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        self.tree.currentItemChanged.connect(self._on_tree_selection_changed)

        # Build tree structure
        self.project_root = QTreeWidgetItem(self.tree, ["未命名项目"])
        self.project_root.setExpanded(True)

        self.geometry_item = QTreeWidgetItem(self.project_root, ["📐 几何"])
        self.geometry_item.setData(0, Qt.UserRole, "geometry")

        self.region_item = QTreeWidgetItem(self.project_root, ["🌍 区域"])
        self.region_item.setData(0, Qt.UserRole, "region")

        self.mesh_item = QTreeWidgetItem(self.project_root, ["🔲 网格"])
        self.mesh_item.setData(0, Qt.UserRole, "mesh")

        self.post_item = QTreeWidgetItem(self.project_root, ["📊 后处理"])
        self.post_item.setData(0, Qt.UserRole, "post")

        self.ai_item = QTreeWidgetItem(self.project_root, ["🤖 AI 助手"])
        self.ai_item.setData(0, Qt.UserRole, "ai")

        left_layout.addWidget(self.tree)

        # --- Center: Stacked workspace ---
        self.workspace = QStackedWidget()
        self.workspace.setStyleSheet("background-color: #0d1117;")

        # Geometry workspace — interactive canvas
        self.geometry_workspace = QWidget()
        geo_layout = QVBoxLayout(self.geometry_workspace)
        geo_layout.setContentsMargins(0, 0, 0, 0)
        geo_layout.setSpacing(0)

        self.geo_toolbar_label = QLabel("点击画布操作 | 长按拖动平移 | 滚轮缩放 | 中键重置视图")
        self.geo_toolbar_label.setStyleSheet(
            "color: #8b949e; font-size: 11px; padding: 6px 12px; background: #161b22; border-bottom: 1px solid #30363d;"
        )
        geo_layout.addWidget(self.geo_toolbar_label)

        self.geo_canvas = InteractiveGeometryCanvas()
        self.geo_canvas.mouse_moved.connect(self._on_geo_mouse_move)
        self.geo_canvas.point_created.connect(self._on_geo_point_created)
        self.geo_canvas.status_changed.connect(self._set_status)
        geo_layout.addWidget(self.geo_canvas, stretch=1)
        self.workspace.addWidget(self.geometry_workspace)

        # Region workspace — flow domain with BCs
        self.region_workspace = QWidget()
        region_layout = QVBoxLayout(self.region_workspace)
        region_layout.setContentsMargins(0, 0, 0, 0)
        region_layout.setSpacing(0)

        region_header = QLabel("区域设置 — 边界条件与流体参数")
        region_header.setStyleSheet(
            "color: #c9d1d9; font-size: 12px; font-weight: 700; padding: 8px 12px; "
            "background: #161b22; border-bottom: 1px solid #30363d;"
        )
        region_layout.addWidget(region_header)

        self.region_canvas = RegionCanvas()
        region_layout.addWidget(self.region_canvas, stretch=1)
        self.workspace.addWidget(self.region_workspace)

        # Mesh workspace
        self.mesh_workspace = QWidget()
        mesh_layout = QVBoxLayout(self.mesh_workspace)
        mesh_layout.setContentsMargins(0, 0, 0, 0)
        mesh_label = QLabel("网格生成\n\n基础尺寸: 100mm | 最小尺寸: 0.1mm\n\n点击菜单栏 [求解] → [开始求解] 生成网格并计算")
        mesh_label.setAlignment(Qt.AlignCenter)
        mesh_label.setStyleSheet("background-color: #161b22; color: #8b949e; font-size: 14px; margin: 8px; border-radius: 4px;")
        mesh_layout.addWidget(mesh_label)
        self.workspace.addWidget(self.mesh_workspace)

        # Post-processing workspace
        self.post_workspace = QWidget()
        post_layout = QVBoxLayout(self.post_workspace)
        post_layout.setContentsMargins(0, 0, 0, 0)
        post_label = QLabel("后处理结果\n\n压力系数云图 | 总压系数云图 | 速度曲线卷积分\n下压力计算\n\n请先在菜单栏点击 [求解] → [开始求解]")
        post_label.setAlignment(Qt.AlignCenter)
        post_label.setStyleSheet("background-color: #161b22; color: #8b949e; font-size: 14px; margin: 8px; border-radius: 4px;")
        post_layout.addWidget(post_label)
        self.workspace.addWidget(self.post_workspace)

        # AI workspace (chat + viz)
        self.ai_workspace = QWidget()
        ai_layout = QHBoxLayout(self.ai_workspace)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(0)

        # Chat in center
        self.chat_widget = ChatWidget(self.ai_client)
        ai_layout.addWidget(self.chat_widget, stretch=2)

        # Viz panels on right
        self.viz_panel = VizPanel()
        self.viz_panel.setFixedWidth(400)
        ai_layout.addWidget(self.viz_panel)

        self.workspace.addWidget(self.ai_workspace)

        # --- Right sidebar: Property panel ---
        self.property_panel = QDockWidget("属性", self)
        self.property_panel.setFixedWidth(280)
        self.property_panel.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.property_panel.setStyleSheet("""
            QDockWidget { background: #0d1117; border-left: 1px solid #30363d; color: #c9d1d9; }
            QDockWidget::title { background: #161b22; padding: 8px 12px;
                border-bottom: 1px solid #30363d; font-weight: 700; font-size: 12px; }
        """)
        prop_content = QWidget()
        prop_layout = QVBoxLayout(prop_content)
        prop_layout.setContentsMargins(12, 12, 12, 12)

        prop_info = QLabel("选择树视图中的节点以查看属性")
        prop_info.setStyleSheet("color: #8b949e; font-size: 12px;")
        prop_info.setWordWrap(True)
        prop_layout.addWidget(prop_info)
        prop_layout.addStretch()

        self.property_panel.setWidget(prop_content)
        self.addDockWidget(Qt.RightDockWidgetArea, self.property_panel)

        # Assemble layout
        main_layout.addWidget(left_widget)
        main_layout.addWidget(self.workspace, stretch=1)

        # Default to AI workspace
        self.workspace.setCurrentWidget(self.ai_workspace)
        self.tree.setCurrentItem(self.ai_item)

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #161b22; color: #8b949e; border-top: 1px solid #30363d;
                font-size: 12px; padding: 4px 10px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 — 选择树视图节点开始")

    def _on_tree_selection_changed(self, current, previous):
        if not current:
            return
        node_type = current.data(0, Qt.UserRole)

        if node_type == "geometry":
            self.workspace.setCurrentWidget(self.geometry_workspace)
            self.toolbar.show()
            self._set_status("几何模块 — 使用工具栏创建和编辑几何元素")
        elif node_type == "region":
            self.workspace.setCurrentWidget(self.region_workspace)
            self.toolbar.hide()
            self._set_status("区域模块 — 设定边界条件和流体参数")
        elif node_type == "mesh":
            self.workspace.setCurrentWidget(self.mesh_workspace)
            self.toolbar.hide()
            self._set_status("网格模块 — 配置网格参数")
        elif node_type == "post":
            self.workspace.setCurrentWidget(self.post_workspace)
            self.toolbar.hide()
            self._set_status("后处理模块 — 查看计算结果")
        elif node_type == "ai":
            self.workspace.setCurrentWidget(self.ai_workspace)
            self.toolbar.hide()
            self._set_status("AI CFD 助手 — 与 AI 专家对话，右侧查看可视化")
        else:
            self.toolbar.hide()

    def _set_status(self, message: str):
        self.status_bar.showMessage(message)

    def _on_geo_mouse_move(self, wx: float, wy: float):
        """Update status bar with world coordinates."""
        if 0 <= wx <= 3000 and 0 <= wy <= 2000:
            self._set_status(f"X={wx:.1f} mm  Y={wy:.1f} mm")
        else:
            self._set_status("几何模块 — 左键拖动平移 | 滚轮缩放 | 右键创建点")

    def _on_geo_point_created(self, wx: float, wy: float):
        self._set_status(f"已创建点: ({wx:.1f}, {wy:.1f}) mm")

    # --- Menu actions ---

    def _on_new(self):
        self.chat_widget.clear_chat()
        self.current_airfoil_data = None
        self.current_airfoil_name = "NACA 2412"
        self.current_result = None
        self.geo_canvas.clear_all()
        self.viz_panel.set_airfoil("2412")
        self._set_status("新项目已创建")

    def _on_import_dat(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入翼型 DAT 文件", "",
            "DAT Files (*.dat);;All Files (*)"
        )
        if path:
            try:
                data = _parse_dat(path)
                if len(data) < 10:
                    raise ValueError("数据点太少，至少需要10个点")
                self.current_airfoil_data = data
                self.current_airfoil_name = os.path.basename(path)
                self._update_viz_with_dat(data)
                self.tree.setCurrentItem(self.geometry_item)
                self._set_status(f"已导入翼型: {os.path.basename(path)} ({len(data)} 点)")
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"无法解析文件: {e}")

    def _update_viz_with_dat(self, data: list):
        """Update visualization panels with imported DAT airfoil data."""
        pts = np.array(data)
        x, y = pts[:, 0], pts[:, 1]
        # Normalize to chord length
        x_min, x_max = x.min(), x.max()
        chord = x_max - x_min
        if chord < 0.001:
            return
        x_norm = (x - x_min) / chord
        y_norm = y / chord
        # Mirror y if mostly negative
        if np.mean(y_norm) < 0:
            y_norm = -y_norm
        # Update geometry canvas
        self.geo_canvas.set_airfoil(x_norm, y_norm, self.current_airfoil_name)
        # Update region canvas
        self.region_canvas.set_airfoil(x_norm, y_norm, self.current_airfoil_name)
        # Update viz panels
        self.viz_panel.airfoil_panel.set_custom_airfoil(x_norm, y_norm, self.current_airfoil_name)
        self.viz_panel.pressure_panel.set_custom_airfoil(x_norm, y_norm, self.current_airfoil_name)
        self.viz_panel.streamline_panel.set_custom_airfoil(x_norm, y_norm, self.current_airfoil_name)

    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "project.cfdproj",
            "CFD Project (*.cfdproj);;All Files (*)"
        )
        if not path:
            return
        try:
            project = {
                "version": "0.1",
                "airfoil_name": self.current_airfoil_name,
                "airfoil_data": self.current_airfoil_data,
                "alpha": self.current_alpha,
                "messages": self.chat_widget.messages[-20:] if hasattr(self, 'chat_widget') else [],
            }
            if self.current_result is not None:
                project["result"] = {
                    "cl": float(self.current_result.cl),
                    "cpm": float(self.current_result.cpm),
                    "cp": self.current_result.cp.tolist(),
                }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(project, f, ensure_ascii=False, indent=2)
            self._set_status(f"项目已保存: {path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _on_export(self):
        if self.current_result is None:
            QMessageBox.information(self, "提示", "请先在求解菜单中运行计算")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", "results.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            r = self.current_result
            with open(path, 'w', encoding='utf-8') as f:
                f.write("近地翼片 2D-CFD 仿真结果\n")
                f.write("=" * 60 + "\n")
                f.write(f"翼型: {self.current_airfoil_name}\n")
                f.write(f"攻角: {self.current_alpha}°\n")
                f.write(f"升力系数 Cl: {r.cl:.4f}\n")
                f.write(f"力矩系数 Cm: {r.cpm:.4f}\n")
                f.write("-" * 60 + "\n")
                f.write(f"{'x/c':>10s}  {'y/c':>10s}  {'Cp':>10s}\n")
                for i in range(len(r.cp)):
                    f.write(f"{r.x_panel[i]:10.4f}  {r.y_panel[i]:10.4f}  {r.cp[i]:10.4f}\n")
            self._set_status(f"结果已导出: {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _on_solve(self):
        self._set_status("正在求解...")
        try:
            from .cfd_core import naca4, panel_method, AirfoilResult
            if self.current_airfoil_data is not None:
                pts = np.array(self.current_airfoil_data)
                x, y = pts[:, 0], pts[:, 1]
                x = (x - x.min()) / (x.max() - x.min() + 1e-12)
                y = y / (x.max() - x.min() + 1e-12)
                n = len(x) // 2
                af = AirfoilResult(
                    x=x, y=y, xu=x[:n], yu=y[:n],
                    xl=x[n:], yl=y[n:], camber=np.zeros(n),
                    naca_code=self.current_airfoil_name,
                )
            else:
                af = naca4("2412", 160)
            self.current_result = panel_method(af, self.current_alpha, 80)
            self._set_status(
                f"求解完成 — Cl={self.current_result.cl:.4f}, Cm={self.current_result.cpm:.4f}"
            )
            self.tree.setCurrentItem(self.post_item)
        except Exception as e:
            self._set_status(f"求解失败: {e}")

    def _on_clear_solve(self):
        self.current_result = None
        self._set_status("求解结果已清除")

    def _on_about(self):
        QMessageBox.about(
            self, "关于",
            "<h3>近地翼片 2D-CFD 仿真</h3>"
            "<p>版本 0.1.0</p>"
            "<p>FSAE 地面效应翼型二维 CFD 快速分析工具</p>"
            "<p>基于面元法求解器 + AI 辅助分析</p>"
            "<p>技术栈: PySide6 + DeepSeek + matplotlib</p>"
        )


def _parse_dat(path: str) -> list[tuple[float, float]]:
    """Parse a Profili-format .dat airfoil file."""
    points = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Skip header lines until we find numeric content
    data_started = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                x, y = float(parts[0]), float(parts[1])
                points.append((x, y))
                data_started = True
            except ValueError:
                if data_started:
                    break
                continue
    return points
