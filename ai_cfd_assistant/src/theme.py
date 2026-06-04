"""Modern dark theme QSS for the AI CFD Assistant."""

QSS = r"""
/* ===== Global ===== */
* {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #0d1117;
}

/* ===== Menu Bar ===== */
QMenuBar {
    background-color: #161b22;
    color: #c9d1d9;
    border-bottom: 1px solid #30363d;
    padding: 2px 0;
}
QMenuBar::item {
    padding: 4px 12px;
    border-radius: 4px;
    margin: 2px 2px;
}
QMenuBar::item:selected {
    background-color: #21262d;
}
QMenu {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 32px 6px 16px;
    border-radius: 4px;
    color: #c9d1d9;
}
QMenu::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #30363d;
    margin: 4px 8px;
}

/* ===== Toolbar ===== */
QToolBar {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 4px;
    spacing: 6px;
}
QToolBar QToolButton {
    color: #c9d1d9;
    border-radius: 6px;
    padding: 5px 10px;
    margin: 1px;
}
QToolBar QToolButton:hover {
    background-color: #21262d;
}
QToolBar QToolButton:pressed {
    background-color: #30363d;
}

/* ===== Status Bar ===== */
QStatusBar {
    background-color: #161b22;
    color: #8b949e;
    border-top: 1px solid #30363d;
    padding: 2px 8px;
}

/* ===== Splitter ===== */
QSplitter::handle {
    background-color: #30363d;
    width: 1px;
    height: 1px;
}
QSplitter::handle:hover {
    background-color: #1f6feb;
}

/* ===== Tree View (Sidebar) ===== */
QTreeWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    border: none;
    outline: none;
}
QTreeWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
    margin: 1px 4px;
    color: #c9d1d9;
}
QTreeWidget::item:hover {
    background-color: #161b22;
}
QTreeWidget::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}
QTreeWidget::branch {
    background-color: transparent;
}
QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    border: none;
    border-bottom: 1px solid #30363d;
    padding: 6px 8px;
    font-weight: bold;
    font-size: 11px;
    text-transform: uppercase;
}

/* ===== Scroll Bars ===== */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #30363d;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #484f58;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ===== Text Input ===== */
QTextEdit, QPlainTextEdit, QLineEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}
QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus {
    border-color: #1f6feb;
    background-color: #0d1117;
}

/* ===== Chat Bubbles (QTextBrowser) ===== */
QTextBrowser {
    background-color: #0d1117;
    color: #c9d1d9;
    border: none;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

/* ===== Buttons ===== */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #484f58;
}
QPushButton:pressed {
    background-color: #161b22;
}
QPushButton#sendButton {
    background-color: #1f6feb;
    border: 1px solid #1f6feb;
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
    min-width: 60px;
}
QPushButton#sendButton:hover {
    background-color: #388bfd;
    border-color: #388bfd;
}
QPushButton#sendButton:pressed {
    background-color: #1a5dcc;
}

/* ===== Group Box ===== */
QGroupBox {
    color: #c9d1d9;
    font-weight: 600;
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #58a6ff;
    font-size: 12px;
    text-transform: uppercase;
}

/* ===== Tab Widget ===== */
QTabWidget::pane {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px;
}
QTabBar::tab {
    background-color: #161b22;
    color: #8b949e;
    border: 1px solid transparent;
    border-radius: 6px 6px 0 0;
    padding: 8px 16px;
    margin-right: 2px;
    font-weight: 500;
}
QTabBar::tab:hover {
    color: #c9d1d9;
    background-color: #21262d;
}
QTabBar::tab:selected {
    color: #58a6ff;
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-bottom: 2px solid #58a6ff;
}

/* ===== Labels ===== */
QLabel#sectionTitle {
    color: #8b949e;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 4px 0;
}

/* ===== Combo Box ===== */
QComboBox {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    min-width: 100px;
}
QComboBox:hover {
    border-color: #484f58;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #c9d1d9;
    selection-background-color: #1f6feb;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 5px 12px;
    border-radius: 4px;
}

/* ===== Spin Box ===== */
QSpinBox, QDoubleSpinBox {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #1f6feb;
}

/* ===== Progress Bar ===== */
QProgressBar {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 3px;
}

/* ===== Tooltip ===== */
QToolTip {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ===== Splitter Handle Style ===== */
QSplitter::handle:horizontal {
    width: 3px;
    background: #30363d;
}
QSplitter::handle:horizontal:hover {
    background: #1f6feb;
}
QSplitter::handle:vertical {
    height: 3px;
    background: #30363d;
}
QSplitter::handle:vertical:hover {
    background: #1f6feb;
}
"""
