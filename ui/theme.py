# -*- coding: utf-8 -*-
"""暗色主题 QSS 与调色板。"""
from __future__ import annotations

# 关键颜色（与 QSS 内保持一致）
BG = "#17181c"
BG_PANEL = "#1e2026"
BG_ELEV = "#262932"
BORDER = "#31353f"
TEXT = "#e6e8ee"
TEXT_DIM = "#9aa0ae"
ACCENT = "#3ea6ff"
ACCENT_HOVER = "#5cb6ff"
GREEN = "#3ddc84"
AMBER = "#ffb84d"
RED = "#ff5c5c"

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
/* 弹窗类（设置对话框、消息框）必须显式深色底，否则继承系统浅色背景导致白字看不见 */
QDialog, QMessageBox {{
    background: {BG_PANEL};
    color: {TEXT};
}}
QDialog QLabel, QMessageBox QLabel {{
    color: {TEXT};
    background: transparent;
}}
QMessageBox {{
    background: {BG_PANEL};
}}
QMessageBox QPushButton {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 18px;
    min-width: 64px;
}}
QMessageBox QPushButton:hover {{
    border-color: {ACCENT};
}}
QMessageBox QPushButton:default {{
    background: {ACCENT};
    border: none;
    color: #fff;
    font-weight: 600;
}}
QWidget#sidebar {{
    background: {BG_PANEL};
    border-right: 1px solid {BORDER};
}}
QWidget#detail {{
    background: {BG};
}}
QLineEdit {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}
QPushButton {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background: #2f333e;
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: #20232b;
}}
QPushButton#primary {{
    background: {ACCENT};
    border: none;
    color: #fff;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#primary:disabled {{
    background: #2b3f52;
    color: #8fa0b3;
}}
QPushButton:disabled {{
    color: #5a606d;
}}
QListWidget {{
    background: {BG_PANEL};
    border: none;
    outline: 0;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 5px;
    margin: 1px 4px;
}}
QListWidget::item:selected {{
    background: {ACCENT};
    color: #fff;
}}
QListWidget::item:hover:!selected {{
    background: #2a2e37;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #3a3f4b;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #4a505e;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QLabel#title {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#subtitle {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
QLabel#section {{
    color: {TEXT_DIM};
    font-size: 12px;
    font-weight: 600;
}}
QFrame#card {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QComboBox {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: 0;
}}
#searchPopup {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
    outline: 0;
}}
#searchPopup::item {{ padding: 6px 8px; border-radius: 4px; }}
#searchPopup::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QStatusBar {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QCheckBox {{ spacing: 8px; }}
QProgressBar {{
    background: {BG_ELEV};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QMenu {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT}; }}
QToolTip {{
    background: {BG_ELEV};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
}}
"""
