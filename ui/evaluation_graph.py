"""Evaluation graph built on pyqtgraph (clickable, Chess.com-like)."""
from __future__ import annotations

from typing import List, Optional, Sequence

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.theme import CLASSIFICATION_COLORS
from core.evaluation import eval_to_plot

pg.setConfigOption("background", "#10161B")
pg.setConfigOption("foreground", "#8E9BA5")
pg.setConfigOptions(antialias=True)


class EvaluationGraph(QWidget):
    """Displays the evaluation after every move of an analysed game."""

    moveSelected = Signal(int)   # ply index (1-based on the x axis -> ply-1)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setMenuEnabled(False)
        self._plot.setMouseEnabled(x=True, y=False)
        self._plot.hideButtons()
        self._plot.showGrid(x=False, y=True, alpha=0.15)
        self._plot.setYRange(-8.5, 8.5, padding=0.0)
        self._plot.setLabel("left", "Evaluation", units="")
        self._plot.setLabel("bottom", "Move")
        self._plot.getAxis("left").setWidth(48)
        layout.addWidget(self._plot)

        self._zero = self._plot.plot([0, 1], [0, 0], pen=pg.mkPen("#3A4652", width=1))

        self._positive_curve = self._plot.plot([], [], pen=None)
        self._negative_curve = self._plot.plot([], [], pen=None)
        self._main_curve = self._plot.plot([], [], pen=pg.mkPen("#E9EEF2", width=2))

        self._fill_white = pg.FillBetweenItem(
            self._positive_curve, self._zero, brush=pg.mkBrush(76, 175, 125, 90)
        )
        self._fill_black = pg.FillBetweenItem(
            self._negative_curve, self._zero, brush=pg.mkBrush(217, 83, 79, 90)
        )
        self._plot.addItem(self._fill_white)
        self._plot.addItem(self._fill_black)

        self._markers = pg.ScatterPlotItem(size=8, pen=pg.mkPen(None))
        self._plot.addItem(self._markers)

        self._cursor = pg.InfiniteLine(
            pos=0, angle=90, movable=False, pen=pg.mkPen("#3D6FD6", width=2)
        )
        self._plot.addItem(self._cursor)

        self._values: List[float] = []
        self._plot.scene().sigMouseClicked.connect(self._on_scene_clicked)

    # ------------------------------------------------------------------
    def set_data(
        self,
        evaluations: Sequence[Optional[float]],
        classifications: Optional[Sequence[str]] = None,
    ) -> None:
        """`evaluations` holds one value per move (already in pawns)."""
        self._values = [float(v) if v is not None else 0.0 for v in evaluations]

        if not self._values:
            self._positive_curve.setData([], [])
            self._negative_curve.setData([], [])
            self._main_curve.setData([], [])
            self._markers.setData([], [])
            self._zero.setData([0, 1], [0, 0])
            return

        xs = list(range(1, len(self._values) + 1))
        ys = self._values

        positive = [max(0.0, value) for value in ys]
        negative = [min(0.0, value) for value in ys]

        self._main_curve.setData(xs, ys)
        self._positive_curve.setData(xs, positive)
        self._negative_curve.setData(xs, negative)
        self._zero.setData([xs[0], xs[-1]], [0, 0])
        self._plot.setXRange(max(1, xs[0]), max(2, xs[-1]), padding=0.02)

        if classifications:
            spots = []
            for index, label in enumerate(classifications):
                if index >= len(xs):
                    break
                color = QColor(CLASSIFICATION_COLORS.get(label, "#8E9BA5"))
                spots.append(
                    {
                        "pos": (xs[index], ys[index]),
                        "brush": pg.mkBrush(color),
                        "pen": pg.mkPen("#10161B", width=1),
                    }
                )
            self._markers.setData(spots)
        else:
            self._markers.setData([], [])

        self._cursor.setPos(0)

    def clear(self) -> None:
        self.set_data([], [])

    def set_cursor(self, ply: int) -> None:
        """`ply` is 0-based; -1 hides the cursor (start position)."""
        if ply < 0 or ply >= len(self._values):
            self._cursor.setPos(0)
            self._cursor.setVisible(False)
        else:
            self._cursor.setVisible(True)
            self._cursor.setPos(ply + 1)

    # ------------------------------------------------------------------
    def _on_scene_clicked(self, event) -> None:
        if not self._values:
            return
        try:
            position = self._plot.plotItem.vb.mapSceneToView(event.scenePos())
        except Exception:
            return
        index = int(round(position.x())) - 1
        index = max(0, min(len(self._values) - 1, index))
        self.moveSelected.emit(index)