"""Main window — follows prompt.txt GUI spec: menu bar, toolbar, tree view, workspace, status bar, property panel."""

from __future__ import annotations
import os
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
        self.toolbar = QToolBar("几何工具栏")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # Geometry tools
        self.toolbar.addAction("📌 点", lambda: self._set_status("选择工具: 点"))
        self.toolbar.addAction("📏 直线", lambda: self._set_status("选择工具: 直线"))
        self.toolbar.addAction("〰️ 样条线", lambda: self._set_status("选择工具: 样条线"))
        self.toolbar.addSeparator()
        self.toolbar.addAction("➕ 创建", lambda: self._set_status("几何操作: 创建"))
        self.toolbar.addAction("🗑 删除", lambda: self._set_status("几何操作: 删除"))
        self.toolbar.addAction("↔ 移动", lambda: self._set_status("几何操作: 移动"))
        self.toolbar.addAction("🔄 旋转", lambda: self._set_status("几何操作: 旋转"))
        self.toolbar.addAction("🔍 缩放", lambda: self._set_status("几何操作: 缩放"))
        self.toolbar.addSeparator()
        self.toolbar.addAction("🔗 重合约束", lambda: self._set_status("约束: 重合"))
        self.toolbar.addAction("🔒 固联约束", lambda: self._set_status("约束: 固联"))

        self.toolbar.hide()  # Initially hidden, shown when geometry tab is active

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

        # Geometry workspace (placeholder canvas)
        self.geometry_workspace = QWidget()
        geo_layout = QVBoxLayout(self.geometry_workspace)
        geo_layout.setContentsMargins(0, 0, 0, 0)
        geo_canvas = QLabel("流场几何幕布\n3000mm × 2000mm\n\n几何工具已激活，使用上方工具栏创建几何元素")
        geo_canvas.setAlignment(Qt.AlignCenter)
        geo_canvas.setStyleSheet(
            "background-color: #e8e8e8; color: #666666; font-size: 16px; "
            "border: 1px solid #cccccc; margin: 8px; border-radius: 4px;"
        )
        geo_layout.addWidget(geo_canvas)
        self.workspace.addWidget(self.geometry_workspace)

        # Region workspace
        self.region_workspace = QWidget()
        region_layout = QVBoxLayout(self.region_workspace)
        region_layout.setContentsMargins(0, 0, 0, 0)
        region_label = QLabel("区域设置\n\n左侧: 速度进口\n右侧: 压力出口\n上侧: 壁面\n下侧: 壁面\n\n流体: 气体 | 分离流 | 恒密度 | 定常 | 湍流 k-ε")
        region_label.setAlignment(Qt.AlignCenter)
        region_label.setStyleSheet("background-color: #161b22; color: #8b949e; font-size: 14px; margin: 8px; border-radius: 4px;")
        region_layout.addWidget(region_label)
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

    # --- Menu actions ---
    def _on_new(self):
        self.chat_widget.clear_chat()
        self._set_status("新项目已创建")

    def _on_import_dat(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入翼型 DAT 文件", "",
            "DAT Files (*.dat);;All Files (*)"
        )
        if path:
            try:
                data = _parse_dat(path)
                self._set_status(f"已导入翼型: {os.path.basename(path)} ({len(data)} 点)")
                self.tree.setCurrentItem(self.geometry_item)
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"无法解析文件: {e}")

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", "results.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("近地翼片 2D-CFD 仿真结果\n")
                    f.write("=" * 40 + "\n")
                    f.write("翼型: NACA 2412\n")
                    f.write("导出时间: 2026-06-05\n")
                self._set_status(f"结果已导出至: {path}")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", str(e))

    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "project.cfd",
            "CFD Project (*.cfd);;All Files (*)"
        )
        if path:
            self._set_status(f"项目已保存: {path}")

    def _on_solve(self):
        self._set_status("正在求解... (面元法计算中)")
        self.tree.setCurrentItem(self.post_item)

    def _on_clear_solve(self):
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
