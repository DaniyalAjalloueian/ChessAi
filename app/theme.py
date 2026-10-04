"""Colour palette, board themes and the global Qt stylesheet."""
from __future__ import annotations

from typing import Dict, Tuple

COLORS: Dict[str, str] = {
    "bg": "#11161B",
    "card": "#171D22",
    "card_alt": "#1C242B",
    "border": "#2E3942",
    "border_soft": "#232C34",
    "primary": "#3D6FD6",
    "primary_hover": "#4B7FE8",
    "primary_pressed": "#335CB0",
    "text": "#E9EEF2",
    "text_muted": "#8E9BA5",
    "success": "#4CAF7D",
    "warning": "#E0A33E",
    "danger": "#D9534F",
    "danger_hover": "#C04843",
}

# (light square, dark square)
BOARD_THEMES: Dict[str, Tuple[str, str]] = {
    "Classic": ("#F0D9B5", "#B58863"),
    "Blue": ("#DEE3E6", "#5C8CB0"),
    "Green": ("#EBECD0", "#739552"),
    "Brown": ("#E8D3B0", "#9A6B4F"),
    "Dark": ("#8B97A3", "#3A4652"),
}

CLASSIFICATION_COLORS: Dict[str, str] = {
    "Best": "#3FA96B",
    "Excellent": "#5FBF7A",
    "Good": "#8FBF6A",
    "Inaccuracy": "#E0A33E",
    "Mistake": "#E07B39",
    "Blunder": "#D9534F",
}

CLASSIFICATION_ORDER = [
    "Best",
    "Excellent",
    "Good",
    "Inaccuracy",
    "Mistake",
    "Blunder",
]


def build_stylesheet() -> str:
    c = COLORS
    return f"""
/* ---------- base ---------- */
QWidget {{
    color: {c['text']};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog, QStackedWidget, QScrollArea, QWidget#Page {{
    background-color: {c['bg']};
}}
QLabel, QCheckBox, QRadioButton {{
    background: transparent;
}}
QToolTip {{
    background-color: {c['card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    padding: 6px 8px;
    border-radius: 6px;
}}

/* ---------- cards / typography ---------- */
QFrame#Card {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}
QFrame#CardFlat {{
    background-color: {c['card_alt']};
    border: 1px solid {c['border_soft']};
    border-radius: 12px;
}}
QLabel#H1 {{ font-size: 32px; font-weight: 700; }}
QLabel#H2 {{ font-size: 20px; font-weight: 600; }}
QLabel#H3 {{ font-size: 15px; font-weight: 600; }}
QLabel#Subtitle {{ color: {c['text_muted']}; font-size: 15px; }}
QLabel#Muted {{ color: {c['text_muted']}; }}
QLabel#SectionTitle {{
    font-size: 11px;
    font-weight: 700;
    color: {c['text_muted']};
    letter-spacing: 1px;
}}
QLabel#EvalBig {{ font-size: 22px; font-weight: 700; }}

/* ---------- buttons ---------- */
QPushButton {{
    background-color: {c['card_alt']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 8px 14px;
    color: {c['text']};
}}
QPushButton:hover {{ background-color: #232C34; border-color: #3B4854; }}
QPushButton:pressed {{ background-color: #1A2229; }}
QPushButton:disabled {{
    color: #5A666F;
    background-color: #151A1F;
    border-color: #222A31;
}}
QPushButton#Primary {{
    background-color: {c['primary']};
    border: 1px solid {c['primary']};
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background-color: {c['primary_hover']}; border-color: {c['primary_hover']}; }}
QPushButton#Primary:pressed {{ background-color: {c['primary_pressed']}; }}
QPushButton#Primary:disabled {{ background-color: #2A3B57; border-color: #2A3B57; color: #7C8B99; }}
QPushButton#Danger {{ background-color: #A83B37; border-color: #A83B37; font-weight: 600; }}
QPushButton#Danger:hover {{ background-color: {c['danger_hover']}; }}
QPushButton#Ghost {{ background-color: transparent; border: 1px solid {c['border']}; }}
QPushButton#Ghost:hover {{ background-color: {c['card_alt']}; }}

QPushButton#MenuCard {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 16px;
    text-align: left;
    padding: 22px;
    font-size: 14px;
}}
QPushButton#MenuCard:hover {{
    background-color: #1C242B;
    border-color: {c['primary']};
}}

/* ---------- inputs ---------- */
QComboBox, QSpinBox, QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: #10161B;
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {c['primary']};
    selection-color: #FFFFFF;
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: #3B4854; }}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {c['primary']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c['text_muted']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    selection-background-color: {c['primary']};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 16px; background: transparent; border: none;
}}

/* ---------- checkbox ---------- */
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {c['border']};
    background: #10161B;
}}
QCheckBox::indicator:hover {{
    border-color: #3B4854;
}}
QCheckBox::indicator:checked {{
    background: {c['primary']};
    border-color: {c['primary']};
}}

/* ---------- slider ---------- */
QSlider::groove:horizontal {{
    height: 4px;
    background: #232C34;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {c['primary']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {c['primary']};
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {c['primary_hover']};
}}
QSlider::handle:horizontal:disabled {{
    background: #3A4652;
}}

/* ---------- tables / lists ---------- */
QTableWidget, QListWidget {{
    background-color: #10161B;
    border: 1px solid {c['border']};
    border-radius: 10px;
    gridline-color: #1E262D;
    outline: none;
}}
QTableWidget::item, QListWidget::item {{
    padding: 4px 6px;
}}
QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {c['primary']};
    color: #FFFFFF;
}}
QHeaderView::section {{
    background-color: {c['card_alt']};
    color: {c['text_muted']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 6px 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background-color: {c['card_alt']}; border: none; }}

/* ---------- scrollbars ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #33404A; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #44535F; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #33404A; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ---------- progress ---------- */
QProgressBar {{
    background-color: #10161B;
    border: 1px solid {c['border']};
    border-radius: 7px;
    text-align: center;
    height: 16px;
    color: {c['text']};
}}
QProgressBar::chunk {{ background-color: {c['primary']}; border-radius: 6px; }}

/* ---------- group box ---------- */
QGroupBox {{
    border: 1px solid {c['border']};
    border-radius: 12px;
    margin-top: 16px;
    padding: 14px 12px 12px 12px;
    background-color: {c['card']};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: {c['text_muted']};
}}

/* ---------- splitter ---------- */
QSplitter::handle {{ background-color: transparent; }}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:vertical {{ height: 10px; }}
"""