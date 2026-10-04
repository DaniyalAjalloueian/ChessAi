"""Move list table shared by the Play and Analysis pages."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.theme import CLASSIFICATION_COLORS

PLY_ROLE = Qt.ItemDataRole.UserRole + 1


class MoveListWidget(QTableWidget):
    """Two-column move list with optional classification colouring."""

    moveActivated = Signal(int)   # 0-based ply

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["#", "White", "Black"])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setAlternatingRowColors(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(0, 44)
        self.verticalHeader().setDefaultSectionSize(28)

        self.cellClicked.connect(self._on_cell_clicked)

        self._classifications: List[str] = []
        self._current_ply = -1

    # ------------------------------------------------------------------
    def set_moves(
        self,
        sans: Sequence[str],
        classifications: Optional[Sequence[str]] = None,
    ) -> None:
        self._classifications = list(classifications) if classifications else []
        self.clearContents()
        self.setRowCount((len(sans) + 1) // 2)
        self._current_ply = -1

        bold = QFont()
        bold.setWeight(QFont.Weight.DemiBold)

        for ply, san in enumerate(sans):
            row = ply // 2
            column = 1 if ply % 2 == 0 else 2

            if column == 1:
                number_item = QTableWidgetItem(f"{row + 1}.")
                number_item.setForeground(QBrush(QColor("#8E9BA5")))
                number_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, 0, number_item)

            item = QTableWidgetItem(san)
            item.setData(PLY_ROLE, ply)
            item.setFont(bold)

            label = self._classifications[ply] if ply < len(self._classifications) else ""
            color = CLASSIFICATION_COLORS.get(label)
            if color:
                item.setForeground(QBrush(QColor(color)))
            self.setItem(row, column, item)

    # ------------------------------------------------------------------
    def set_current_ply(self, ply: int) -> None:
        self._current_ply = ply
        if ply < 0 or self.rowCount() == 0:
            self.clearSelection()
            return
        row = ply // 2
        column = 1 if ply % 2 == 0 else 2
        item = self.item(row, column)
        if item is not None:
            self.blockSignals(True)
            self.setCurrentItem(item)
            self.blockSignals(False)
            self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    # ------------------------------------------------------------------
    def _on_cell_clicked(self, row: int, column: int) -> None:
        if column == 0:
            return
        item = self.item(row, column)
        if item is None:
            return
        ply = item.data(PLY_ROLE)
        if ply is None:
            return
        self.moveActivated.emit(int(ply))

    # ------------------------------------------------------------------
    def current_ply(self) -> int:
        return self._current_ply