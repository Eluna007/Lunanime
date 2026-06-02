DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #0f0f13;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* Sidebar */
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
#sidebar QPushButton:hover {
    background-color: #1e1e2e;
    color: #e0e0e0;
}
#sidebar QPushButton[active="true"] {
    background-color: #1e1e2e;
    color: #c084fc;
    border-left: 3px solid #c084fc;
}

/* Search bar */
QLineEdit {
    background-color: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #c084fc;
}

/* Buttons */
QPushButton {
    background-color: #c084fc;
    color: #0f0f13;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #d8a4ff;
}
QPushButton:pressed {
    background-color: #a855f7;
}
QPushButton:disabled {
    background-color: #2a2a3a;
    color: #555566;
}

/* Flat button variant */
QPushButton[flat="true"] {
    background: transparent;
    color: #c084fc;
    border: 1px solid #c084fc;
}
QPushButton[flat="true"]:hover {
    background-color: #1e1e2e;
}

/* ComboBox */
QComboBox {
    background-color: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e0e0;
    min-width: 130px;
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

/* Scroll areas */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #16161e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2a2a3a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #c084fc; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* Cards */
#animeCard {
    background-color: #16161e;
    border: 1px solid #2a2a3a;
    border-radius: 10px;
}
#animeCard:hover {
    border: 1px solid #c084fc;
    background-color: #1a1a2a;
}

/* Episode list */
QListWidget {
    background-color: #16161e;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    outline: none;
}
QListWidget::item {
    padding: 10px 14px;
    border-bottom: 1px solid #1e1e2e;
    color: #e0e0e0;
}
QListWidget::item:hover { background-color: #1e1e2e; }
QListWidget::item:selected {
    background-color: #2d1e4e;
    color: #c084fc;
}

/* Labels */
QLabel { color: #e0e0e0; }
#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}
#subtitleLabel {
    font-size: 12px;
    color: #707080;
}
#sectionLabel {
    font-size: 15px;
    font-weight: bold;
    color: #c084fc;
}
#statusBadge {
    background-color: #2d1e4e;
    color: #c084fc;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
}

/* Loading spinner label */
#loadingLabel {
    color: #707080;
    font-size: 14px;
}

/* Settings */
QGroupBox {
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
    color: #9090a0;
    font-size: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #c084fc;
}

/* Splitter */
QSplitter::handle { background-color: #2a2a3a; width: 1px; }

/* Tab bar (if used) */
QTabBar::tab {
    background: #16161e;
    color: #9090a0;
    padding: 8px 16px;
    border: none;
}
QTabBar::tab:selected {
    color: #c084fc;
    border-bottom: 2px solid #c084fc;
    background: #1e1e2e;
}
"""
