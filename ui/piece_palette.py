"""Reusable piece palette for editing positions on the board."""
from __future__ import annotations

from typing import Optional, Tuple

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.chess_board import BLACK_PIECE_GLYPHS, WHITE_PIECE_GLYPHS

PIECE_ORDER = [
    (chess.KING, "K"),
    (chess.QUEEN, "Q"),
    (chess.ROOK, "R"),
    (chess.BISHOP, "B"),
    (chess.KNIGHT, "N"),
    (chess.PAWN, "P"),
]


_BUTTON_STYLE_LIGHT = """
QPushButton {
    background-color: #10161B;
    border: 1px solid #2E3942;
    border-radius: 7px;
    font-size: 22px;
    color: #E9EEF2;
    padding: 0;
}
QPushButton:hover { border-color: #3D6FD6; }
QPushButton:checked {
    background-color: #3D6FD6;
    border: 2px solid #4B7FE8;
    color: #FFFFFF;
}
"""

_BUTTON_STYLE_DARK = """
QPushButton {
    background-color: #10161B;
    border: 1px solid #2E3942;
    border-radius: 7px;
    font-size: 22px;
    color: #8E9BA5;
    padding: 0;
}
QPushButton:hover { border-color: #3D6FD6; }
QPushButton:checked {
    background-color: #3D6FD6;
    border: 2px solid #4B7FE8;
    color: #FFFFFF;
}
"""


class PiecePalette(QWidget):
    """Grid of piece buttons + eraser + free-move toggle."""

    pieceSelected = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._active: object = None  # (piece_type, color) | "eraser" | None
        self._buttons: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # ---- White row ------------------------------------------------
        outer.addWidget(self._section_label("White pieces"))
        white_row = QHBoxLayout()
        white_row.setSpacing(4)
        for piece_type, letter in PIECE_ORDER:
            btn = self._make_button(
                WHITE_PIECE_GLYPHS[letter],
                (piece_type, chess.WHITE),
                _BUTTON_STYLE_LIGHT,
            )
            white_row.addWidget(btn)
        white_row.addStretch(1)
        outer.addLayout(white_row)

        # ---- Black row ------------------------------------------------
        outer.addWidget(self._section_label("Black pieces"))
        black_row = QHBoxLayout()
        black_row.setSpacing(4)
        for piece_type, letter in PIECE_ORDER:
            btn = self._make_button(
                BLACK_PIECE_GLYPHS[letter],
                (piece_type, chess.BLACK),
                _BUTTON_STYLE_DARK,
            )
            black_row.addWidget(btn)
        black_row.addStretch(1)
        outer.addLayout(black_row)

        # ---- Tools row ------------------------------------------------
        outer.addWidget(self._section_label("Tools"))
        tools = QHBoxLayout()
        tools.setSpacing(4)

        eraser = QPushButton("\u232B")
        eraser.setStyleSheet(_BUTTON_STYLE_LIGHT)
        eraser.setCheckable(True)
        eraser.setFixedSize(38, 38)
        eraser.setToolTip("Erase: click a square to remove the piece on it")
        eraser.clicked.connect(lambda: self._toggle(eraser, "eraser"))
        tools.addWidget(eraser)
        self._buttons["eraser"] = eraser

        move = QPushButton("\u2194")
        move.setStyleSheet(_BUTTON_STYLE_LIGHT)
        move.setCheckable(True)
        move.setFixedSize(38, 38)
        move.setToolTip("Move: drag existing pieces freely between squares")
        move.clicked.connect(lambda: self._toggle(move, None))
        tools.addWidget(move)
        self._buttons["move"] = move

        tools.addStretch(1)
        outer.addLayout(tools)

        # ---- Default: move mode --------------------------------------
        move.setChecked(True)
        self._active = None

    # ------------------------------------------------------------------
    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Muted")
        label.setStyleSheet("font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        return label

    def _make_button(self, glyph: str, value, style: str) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setStyleSheet(style)
        btn.setCheckable(True)
        btn.setFixedSize(38, 38)
        btn.clicked.connect(lambda: self._toggle(btn, value))
        self._buttons[value] = btn
        return btn

    # ------------------------------------------------------------------
    def _toggle(self, button: QPushButton, value) -> None:
        if button.isChecked():
            for key, other in self._buttons.items():
                if other is not button:
                    other.setChecked(False)
            self._active = value
            self.pieceSelected.emit(value)
            return

        # Clicking the active button again → revert to free-move mode.
        self._active = None
        move_btn = self._buttons.get("move")
        if move_btn is not None:
            move_btn.setChecked(True)
        self.pieceSelected.emit(None)

    # ------------------------------------------------------------------
    def active(self):
        return self._active

    def clear_selection(self) -> None:
        for btn in self._buttons.values():
            btn.setChecked(False)
        move_btn = self._buttons.get("move")
        if move_btn is not None:
            move_btn.setChecked(True)
        self._active = None
        self.pieceSelected.emit(None)