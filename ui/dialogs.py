"""Reusable dialogs and small message helpers."""
from __future__ import annotations

from typing import Optional, Tuple

import chess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.theme import CLASSIFICATION_COLORS

PIECE_LABELS = [
    (chess.QUEEN, "\u265B", "Queen"),
    (chess.ROOK, "\u265C", "Rook"),
    (chess.BISHOP, "\u265D", "Bishop"),
    (chess.KNIGHT, "\u265E", "Knight"),
]


# ----------------------------------------------------------------------
def info(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def warn(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.warning(parent, title, text)


def error(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)


def confirm(parent: Optional[QWidget], title: str, text: str) -> bool:
    result = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return result == QMessageBox.StandardButton.Yes


# ----------------------------------------------------------------------
class PromotionDialog(QDialog):
    """Asks the user which piece a pawn should promote to."""

    def __init__(self, color: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pawn Promotion")
        self.setModal(True)
        self._piece: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Choose a promotion piece")
        title.setObjectName("H3")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        for index, (piece_type, glyph, name) in enumerate(PIECE_LABELS):
            button = QPushButton(f"{glyph}  {name}")
            button.setMinimumHeight(52)
            button.clicked.connect(lambda _=False, p=piece_type: self._choose(p))
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def _choose(self, piece_type: int) -> None:
        self._piece = piece_type
        self.accept()

    def selected_piece(self) -> Optional[int]:
        return self._piece


def ask_promotion(parent: Optional[QWidget], color: bool) -> Optional[int]:
    dialog = PromotionDialog(color, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_piece()
    return None


# ----------------------------------------------------------------------
class FenDialog(QDialog):
    """Load a position from a FEN string."""

    def __init__(self, current_fen: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Load FEN")
        self.setMinimumWidth(560)
        self._fen: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        label = QLabel("Paste a FEN string below:")
        layout.addWidget(label)

        self._edit = QPlainTextEdit(current_fen)
        self._edit.setFixedHeight(84)
        layout.addWidget(self._edit)

        buttons = QDialogButtonBox()
        load_button = buttons.addButton("Load", QDialogButtonBox.ButtonRole.AcceptRole)
        load_button.setObjectName("Primary")
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def fen(self) -> Optional[str]:
        return self._fen

    def accept(self) -> None:
        self._fen = self._edit.toPlainText().strip()
        super().accept()


# ----------------------------------------------------------------------
class PgnDialog(QDialog):
    """Paste PGN text for analysis."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paste PGN")
        self.setMinimumSize(620, 460)
        self._text: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Paste a complete PGN game below:"))
        self._edit = QTextEdit()
        self._edit.setPlaceholderText(
            '[Event "Casual Game"]\n[White "Player"]\n[Black "Opponent"]\n\n'
            "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"
        )
        layout.addWidget(self._edit)

        buttons = QDialogButtonBox()
        load_button = buttons.addButton("Analyze Game", QDialogButtonBox.ButtonRole.AcceptRole)
        load_button.setObjectName("Primary")
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def pgn(self) -> Optional[str]:
        return self._text

    def accept(self) -> None:
        self._text = self._edit.toPlainText()
        super().accept()


# ----------------------------------------------------------------------
class GameSummaryDialog(QDialog):
    """Displays the post-analysis summary."""

    def __init__(self, result, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Game Summary")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        heading = QLabel("Game Summary")
        heading.setObjectName("H2")
        layout.addWidget(heading)

        note = QLabel(
            "Classifications are produced by this application's own engine-based "
            "metric and are not identical to any commercial website's algorithm."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        white_accuracy = QLabel(f"White Accuracy: {result.white.accuracy:.1f}%")
        black_accuracy = QLabel(f"Black Accuracy: {result.black.accuracy:.1f}%")
        white_accuracy.setObjectName("H3")
        black_accuracy.setObjectName("H3")
        layout.addWidget(white_accuracy)
        layout.addWidget(black_accuracy)

        for title, summary in (("White", result.white), ("Black", result.black)):
            block = QLabel(
                f"<b>{title}</b><br>"
                f"Best: {summary.best}<br>"
                f"Excellent: {summary.excellent}<br>"
                f"Good: {summary.good}<br>"
                f"Inaccuracies: {summary.inaccuracy}<br>"
                f"Mistakes: {summary.mistake}<br>"
                f"Blunders: {summary.blunder}"
            )
            block.setWordWrap(True)
            layout.addWidget(block)

        buttons = QDialogButtonBox()
        buttons.addButton("Close", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)