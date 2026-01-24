"""
Styles and themes for LabIndex.

Dark theme matching PhysioMetrics style.
"""

# Dark theme colors
COLORS = {
    "bg_primary": "#1e1e1e",
    "bg_secondary": "#252526",
    "bg_tertiary": "#2d2d30",
    "bg_hover": "#3e3e42",
    "text_primary": "#d4d4d4",
    "text_secondary": "#888888",
    "accent": "#4fc3f7",
    "accent_hover": "#80d8ff",
    "success": "#2e7d32",
    "warning": "#f57c00",
    "error": "#c62828",
    "border": "#3e3e42",
    "selection": "#264f78",
    "readonly_indicator": "#007acc",
}

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", sans-serif;
}

QGroupBox {
    border: 1px solid #3e3e42;
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #4fc3f7;
}

QTabWidget::pane {
    border: 1px solid #3e3e42;
    border-radius: 3px;
}
QTabBar::tab {
    background-color: #2d2d30;
    color: #d4d4d4;
    padding: 10px 24px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #4fc3f7;
    border-bottom: 2px solid #4fc3f7;
}
QTabBar::tab:hover:!selected {
    background-color: #3e3e42;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    gridline-color: #3e3e42;
    selection-background-color: #264f78;
    alternate-background-color: #252526;
    border: 1px solid #3e3e42;
}
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #264f78;
}

QHeaderView::section {
    background-color: #2d2d30;
    color: #4fc3f7;
    padding: 6px;
    border: none;
    border-right: 1px solid #3e3e42;
    border-bottom: 1px solid #3e3e42;
    font-weight: bold;
}

QPushButton {
    background-color: #3c3c3c;
    color: #d4d4d4;
    padding: 8px 16px;
    border-radius: 4px;
    border: 1px solid #3e3e42;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #4a4a4a;
    border-color: #505050;
}
QPushButton:pressed {
    background-color: #2d2d30;
}
QPushButton:disabled {
    background-color: #2d2d30;
    color: #6e6e6e;
}

QPushButton#primaryButton {
    background-color: #0e639c;
    color: white;
    border: none;
}
QPushButton#primaryButton:hover {
    background-color: #1177bb;
}

QPushButton#successButton {
    background-color: #2e7d32;
    color: white;
    border: none;
}
QPushButton#successButton:hover {
    background-color: #388e3c;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 6px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #4fc3f7;
}

QLineEdit#searchBox {
    font-size: 14px;
    padding: 10px 14px;
    border-radius: 6px;
}

QComboBox {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 6px 10px;
    min-width: 100px;
}
QComboBox:focus {
    border-color: #4fc3f7;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d30;
    color: #d4d4d4;
    selection-background-color: #264f78;
    border: 1px solid #3e3e42;
}

QScrollBar:vertical {
    background: #1e1e1e;
    width: 12px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #5a5a5a;
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #6e6e6e;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #1e1e1e;
    height: 12px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #5a5a5a;
    border-radius: 4px;
    min-width: 30px;
    margin: 2px;
}

QSplitter::handle {
    background-color: #3e3e42;
}
QSplitter::handle:vertical {
    height: 4px;
}
QSplitter::handle:horizontal {
    width: 4px;
}

QStatusBar {
    background-color: #007acc;
    color: white;
    padding: 4px;
}

QProgressBar {
    background-color: #3c3c3c;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    text-align: center;
    color: white;
}
QProgressBar::chunk {
    background-color: #4fc3f7;
    border-radius: 3px;
}

QToolTip {
    background-color: #2d2d30;
    color: #d4d4d4;
    border: 1px solid #3e3e42;
    padding: 4px;
}

/* Read-only indicator label */
QLabel#readOnlyIndicator {
    background-color: #007acc;
    color: white;
    padding: 4px 12px;
    border-radius: 4px;
    font-weight: bold;
}
"""
