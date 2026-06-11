DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #0f0f13;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
#sidebar {
    background-color: #16161e;
    border-right: 1px solid #2a2a3a;
    min-width: 180px;
    max-width: 180px;
}
#sidebar QPushButton {
    background: transparent;
    border: none;
    color: #9090a0;
    text-align: left;
    padding: 12px 20px;
    font-size: 13px;
    border-radius: 0;
}
#sidebar QPushButton:hover { background-color: #1e1e2e; color: #e0e0e0; }
#sidebar QPushButton[active="true"] {
    background-color: #1e1e2e;
    color: #c084fc;
    border-left: 3px solid #c084fc;
}
QLineEdit {
    background-color: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 14px;
}
QLineEdit:focus { border: 1px solid #c084fc; }
QPushButton {
    background-color: #c084fc;
    color: #0f0f13;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover { background-color: #d8a4ff; }
QPushButton:pressed { background-color: #a855f7; }
QPushButton:disabled { background-color: #2a2a3a; color: #555566; }
QPushButton[flat="true"] { background: transparent; color: #c084fc; border: 1px solid #c084fc; }
QPushButton[flat="true"]:hover { background-color: #1e1e2e; }
QPushButton[danger="true"] { background-color: #7f1d1d; color: #fca5a5; }
QPushButton[danger="true"]:hover { background-color: #991b1b; }
QComboBox {
    background-color: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e0e0;
    min-width: 110px;
}
QComboBox:hover { border: 1px solid #c084fc; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    border: 1px solid #2a2a3a;
    color: #e0e0e0;
    selection-background-color: #c084fc;
    selection-color: #0f0f13;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #16161e; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #2a2a3a; border-radius: 4px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #c084fc; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #16161e; height: 8px; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #2a2a3a; border-radius: 4px; min-width: 20px; }
QScrollBar::handle:horizontal:hover { background: #c084fc; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
#animeCard { background-color: #16161e; border: 1px solid #2a2a3a; border-radius: 10px; }
#animeCard:hover { border: 1px solid #c084fc; background-color: #1a1a2a; }
QListWidget {
    background-color: #16161e;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    outline: none;
}
QListWidget::item { padding: 10px 14px; border-bottom: 1px solid #1e1e2e; color: #e0e0e0; }
QListWidget::item:hover { background-color: #1e1e2e; }
QListWidget::item:selected { background-color: #2d1e4e; color: #c084fc; }
QLabel { color: #e0e0e0; }
#titleLabel { font-size: 18px; font-weight: bold; color: #ffffff; }
#subtitleLabel { font-size: 12px; color: #707080; }
#sectionLabel { font-size: 15px; font-weight: bold; color: #c084fc; }
#statusBadge { background-color: #2d1e4e; color: #c084fc; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
QGroupBox {
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
    color: #9090a0;
    font-size: 12px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #c084fc; }
QSplitter::handle { background-color: #2a2a3a; width: 1px; }
QProgressBar {
    background-color: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e0;
    height: 16px;
}
QProgressBar::chunk { background-color: #c084fc; border-radius: 4px; }
QCheckBox { color: #e0e0e0; spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #2a2a3a; border-radius: 3px; background: #1e1e2e; }
QCheckBox::indicator:checked { background: #c084fc; border-color: #c084fc; }
QTabBar::tab { background: #16161e; color: #9090a0; padding: 8px 16px; border: none; }
QTabBar::tab:selected { color: #c084fc; border-bottom: 2px solid #c084fc; background: #1e1e2e; }
"""

LIGHT_STYLE = """
QMainWindow, QWidget {
    background-color: #f5f5f7;
    color: #1a1a2e;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
#sidebar {
    background-color: #ffffff;
    border-right: 1px solid #e0e0e0;
    min-width: 180px;
    max-width: 180px;
}
#sidebar QPushButton {
    background: transparent;
    border: none;
    color: #606070;
    text-align: left;
    padding: 12px 20px;
    font-size: 13px;
    border-radius: 0;
}
#sidebar QPushButton:hover { background-color: #f0f0f5; color: #1a1a2e; }
#sidebar QPushButton[active="true"] {
    background-color: #f0f0f5;
    color: #7c3aed;
    border-left: 3px solid #7c3aed;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d0d0d8;
    border-radius: 8px;
    padding: 8px 12px;
    color: #1a1a2e;
    font-size: 14px;
}
QLineEdit:focus { border: 1px solid #7c3aed; }
QPushButton {
    background-color: #7c3aed;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover { background-color: #6d28d9; }
QPushButton:pressed { background-color: #5b21b6; }
QPushButton:disabled { background-color: #e0e0e0; color: #a0a0a0; }
QPushButton[flat="true"] { background: transparent; color: #7c3aed; border: 1px solid #7c3aed; }
QPushButton[flat="true"]:hover { background-color: #f5f0ff; }
QPushButton[danger="true"] { background-color: #fee2e2; color: #dc2626; }
QPushButton[danger="true"]:hover { background-color: #fecaca; }
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d8;
    border-radius: 6px;
    padding: 6px 12px;
    color: #1a1a2e;
    min-width: 110px;
}
QComboBox:hover { border: 1px solid #7c3aed; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d0d0d8;
    color: #1a1a2e;
    selection-background-color: #7c3aed;
    selection-color: #ffffff;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f0f0f5; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #c0c0cc; border-radius: 4px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #7c3aed; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #f0f0f5; height: 8px; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #c0c0cc; border-radius: 4px; min-width: 20px; }
QScrollBar::handle:horizontal:hover { background: #7c3aed; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
#animeCard { background-color: #ffffff; border: 1px solid #e0e0e8; border-radius: 10px; }
#animeCard:hover { border: 1px solid #7c3aed; background-color: #faf8ff; }
QListWidget {
    background-color: #ffffff;
    border: 1px solid #e0e0e8;
    border-radius: 8px;
    outline: none;
}
QListWidget::item { padding: 10px 14px; border-bottom: 1px solid #f0f0f5; color: #1a1a2e; }
QListWidget::item:hover { background-color: #f5f0ff; }
QListWidget::item:selected { background-color: #ede9fe; color: #7c3aed; }
QLabel { color: #1a1a2e; }
#titleLabel { font-size: 18px; font-weight: bold; color: #0f0f1a; }
#subtitleLabel { font-size: 12px; color: #808090; }
#sectionLabel { font-size: 15px; font-weight: bold; color: #7c3aed; }
#statusBadge { background-color: #ede9fe; color: #7c3aed; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
QGroupBox {
    border: 1px solid #e0e0e8;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
    color: #808090;
    font-size: 12px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #7c3aed; }
QSplitter::handle { background-color: #e0e0e8; width: 1px; }
QProgressBar {
    background-color: #f0f0f5;
    border: 1px solid #e0e0e8;
    border-radius: 4px;
    text-align: center;
    color: #1a1a2e;
    height: 16px;
}
QProgressBar::chunk { background-color: #7c3aed; border-radius: 4px; }
QCheckBox { color: #1a1a2e; spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #d0d0d8; border-radius: 3px; background: #ffffff; }
QCheckBox::indicator:checked { background: #7c3aed; border-color: #7c3aed; }
QTabBar::tab { background: #ffffff; color: #808090; padding: 8px 16px; border: none; }
QTabBar::tab:selected { color: #7c3aed; border-bottom: 2px solid #7c3aed; background: #f5f0ff; }
"""
