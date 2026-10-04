"""Vertical evaluation bar (White at the bottom by default)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from core.evaluation import advantage_fraction


class EvaluationBar(QWidget):
    """A slim vertical bar that visualises White's share of the evaluation."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(34)
        self.setMinimumHeight(240)
        self._fraction = 0.5
        self._text = "0.00"
        self._flipped = False

    # ------------------------------------------------------------------
    def set_score(self, cp: Optional[int], mate: Optional[int]) -> None:
        self._fraction = advantage_fraction(cp, mate)
        if mate is not None:
            if mate == 0:
                self._text = "#"
            else:
                self._text = f"M{abs(mate)}" if mate > 0 else f"-M{abs(mate)}"
        elif cp is None:
            self._text = "0.00"
        else:
            self._text = f"{cp / 100.0:+.2f}"
        self.update()

    def set_flipped(self, flipped: bool) -> None:
        self._flipped = flipped
        self.update()

    def reset(self) -> None:
        self.set_score(0, None)

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        radius = rect.width() / 2.0

        # Black background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#20262C"))
        painter.drawRoundedRect(rect, radius, radius)

        fraction = self._fraction
        if self._flipped:
            fraction = 1.0 - fraction

        white_height = rect.height() * fraction
        if white_height > 0.5:
            white_rect = QRectF(rect.left(), rect.bottom() - white_height, rect.width(), white_height)
            painter.save()
            path_rect = QRectF(rect)
            painter.setClipRect(path_rect)
            painter.setBrush(QColor("#F2F5F7"))
            painter.drawRoundedRect(rect, radius, radius)
            painter.restore()

            # Re-paint the black part on top of the rounded white shape.
            if white_height < rect.height():
                black_rect = QRectF(rect.left(), rect.top(), rect.width(), rect.height() - white_height)
                painter.setBrush(QColor("#20262C"))
                painter.drawRoundedRect(rect, radius, radius)
                painter.setBrush(QColor("#F2F5F7"))
                painter.drawRoundedRect(
                    QRectF(rect.left(), rect.bottom() - white_height, rect.width(), white_height),
                    radius, radius,
                )

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#3A4652"), 1))
        painter.drawRoundedRect(rect, radius, radius)

        # Score label
        font = QFont("Segoe UI", 9)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#E9EEF2"))
        text_rect = QRectF(0, rect.center().y() - 10, self.width(), 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()