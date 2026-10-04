"""Landing page with the three main entry cards."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MenuCard(QFrame):
    """A large clickable card."""

    clicked = Signal()

    def __init__(self, glyph: str, title: str, description: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(170)
        self.setMinimumWidth(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(10)

        icon = QLabel(glyph)
        icon.setStyleSheet("font-size: 34px;")
        layout.addWidget(icon)

        heading = QLabel(title)
        heading.setObjectName("H2")
        layout.addWidget(heading)

        body = QLabel(description)
        body.setObjectName("Muted")
        body.setWordWrap(True)
        layout.addWidget(body)

        layout.addStretch(1)

        call_to_action = QLabel("Open  \u2192")
        call_to_action.setStyleSheet("color: #3D6FD6; font-weight: 600;")
        layout.addWidget(call_to_action)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HomePage(QWidget):
    """The application's main menu."""

    requestNavigate = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(56, 46, 56, 40)
        root.setSpacing(26)

        header = QVBoxLayout()
        header.setSpacing(6)

        title = QLabel("Local Chess AI")
        title.setObjectName("H1")
        header.addWidget(title)

        subtitle = QLabel("Powerful offline chess analysis powered by Stockfish")
        subtitle.setObjectName("Subtitle")
        header.addWidget(subtitle)

        root.addLayout(header)
        root.addSpacing(6)

        cards = QHBoxLayout()
        cards.setSpacing(22)

        self.play_card = MenuCard(
            "\u265A",
            "Play vs Engine",
            "Play a complete game against Stockfish.",
        )
        self.play_card.clicked.connect(lambda: self.requestNavigate.emit("play"))

        self.best_move_card = MenuCard(
            "\u265B",
            "Calculate Best Move",
            "Analyze a position and find the strongest continuation.",
        )
        self.best_move_card.clicked.connect(lambda: self.requestNavigate.emit("bestmove"))

        self.analysis_card = MenuCard(
            "\u265E",
            "Game Analysis",
            "Analyze a complete PGN game with an evaluation graph.",
        )
        self.analysis_card.clicked.connect(lambda: self.requestNavigate.emit("analysis"))

        for card in (self.play_card, self.best_move_card, self.analysis_card):
            cards.addWidget(card)

        root.addLayout(cards, 1)

        footer = QHBoxLayout()
        footer.setSpacing(12)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("Ghost")
        self.settings_button.setMinimumHeight(40)
        self.settings_button.clicked.connect(lambda: self.requestNavigate.emit("settings"))
        footer.addWidget(self.settings_button)

        footer.addStretch(1)

        hint = QLabel("Runs 100% offline \u2014 no internet connection required")
        hint.setObjectName("Muted")
        footer.addWidget(hint)

        footer.addStretch(1)

        self.exit_button = QPushButton("Exit")
        self.exit_button.setObjectName("Ghost")
        self.exit_button.setMinimumHeight(40)
        self.exit_button.clicked.connect(self._exit_application)
        footer.addWidget(self.exit_button)

        root.addLayout(footer)

    # ------------------------------------------------------------------
    def _exit_application(self) -> None:
        window = self.window()
        if window is not None:
            window.close()