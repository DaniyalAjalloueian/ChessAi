"""Analyse a single position and show the best continuations (MultiPV)."""
from __future__ import annotations

from typing import List, Optional

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.sounds import SoundManager
from app.utils import human_int
from core.fen import validate_fen, set_side_to_move
from engine.analysis import pv_to_san
from engine.engine_manager import EngineManager, EngineTask
from ui import dialogs
from ui.chess_board import ChessBoardWidget
from ui.piece_palette import PiecePalette

THINKING_TIMES = {
    "Unlimited": None,
    "0.1 sec": 0.1,
    "0.25 sec": 0.25,
    "0.5 sec": 0.5,
    "1 sec": 1.0,
    "2 sec": 2.0,
    "5 sec": 5.0,
    "10 sec": 10.0,
    "30 sec": 30.0,
}


def _scrolled(widget: QWidget, min_width: int = 340, max_width: int = 520) -> QScrollArea:
    """Wrap `widget` in a styled, resizable scroll area."""
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setMinimumWidth(min_width)
    area.setMaximumWidth(max_width)
    area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    return area


class BestMovePage(QWidget):
    """Find the strongest continuation for an arbitrary position."""

    requestNavigate = Signal(str)

    def __init__(
        self,
        engine_manager: EngineManager,
        config,
        sounds: SoundManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._engine_manager = engine_manager
        self._config = config
        self._sounds = sounds

        self._board = chess.Board()
        self._task: Optional[EngineTask] = None
        self._lines: List[object] = []

        self._build_ui()
        self.refresh_settings()
        self._sync_board()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(10)
        outer.addWidget(self._splitter)

        # ---------------- Left: board ---------------------------------
        board_container = QWidget()
        board_column = QVBoxLayout(board_container)
        board_column.setContentsMargins(4, 4, 4, 4)
        board_column.setSpacing(10)

        self.board_widget = ChessBoardWidget()
        self.board_widget.set_promotion_callback(lambda *_: chess.QUEEN)
        self.board_widget.moveRequested.connect(self._on_board_move)
        self.board_widget.positionEdited.connect(self._on_board_edited)
        board_column.addWidget(self.board_widget, 1)

        self.status_label = QLabel("Set up a position, then press Analyze.")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        board_column.addWidget(self.status_label)

        self._splitter.addWidget(board_container)

        # ---------------- Right: panel (scrollable) -------------------
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 4, 6, 4)
        panel_layout.setSpacing(12)

        panel_layout.addWidget(self._build_position_group())
        panel_layout.addWidget(self._build_edit_group())
        panel_layout.addWidget(self._build_engine_group())

        results_frame = QGroupBox("Candidate Moves")
        results_layout = QVBoxLayout(results_frame)
        results_layout.setSpacing(8)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["#", "Move", "Eval", "Principal Variation"])
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.results_table.setColumnWidth(0, 36)
        self.results_table.setColumnWidth(1, 78)
        self.results_table.setColumnWidth(2, 74)
        self.results_table.setMinimumHeight(180)
        self.results_table.itemSelectionChanged.connect(self._on_line_selected)
        results_layout.addWidget(self.results_table)

        self.info_label = QLabel("Depth: -   Nodes: -   NPS: -")
        self.info_label.setObjectName("Muted")
        results_layout.addWidget(self.info_label)

        panel_layout.addWidget(results_frame, 1)

        self._splitter.addWidget(_scrolled(panel, min_width=400, max_width=580))
        self._splitter.setStretchFactor(0, 5)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setSizes([820, 520])

    # ------------------------------------------------------------------
    def _build_position_group(self) -> QGroupBox:
        group = QGroupBox("Position")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.fen_edit = QLineEdit()
        self.fen_edit.setPlaceholderText("Paste a FEN string here")
        layout.addWidget(self.fen_edit)

        row = QHBoxLayout()
        for label, handler in (
            ("Load FEN", self.load_fen),
            ("Copy FEN", self.copy_fen),
            ("Reset", self.reset_position),
            ("Flip Board", self.flip_board),
        ):
            button = QPushButton(label)
            button.setMinimumHeight(32)
            button.clicked.connect(handler)
            row.addWidget(button)
        layout.addLayout(row)

        side_row = QHBoxLayout()
        side_row.addWidget(QLabel("Side to Move:"))
        self.side_combo = QComboBox()
        self.side_combo.addItems(["White", "Black"])
        self.side_combo.currentTextChanged.connect(self._on_side_changed)
        side_row.addWidget(self.side_combo, 1)
        layout.addLayout(side_row)

        return group

    # ------------------------------------------------------------------
    def _build_edit_group(self) -> QGroupBox:
        group = QGroupBox("Edit Position")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        self.edit_toggle = QPushButton("Edit Position")
        self.edit_toggle.setCheckable(True)
        self.edit_toggle.setMinimumHeight(34)
        self.edit_toggle.setStyleSheet(
            "QPushButton:checked {"
            " background-color: #3D6FD6;"
            " border: 2px solid #4B7FE8;"
            " color: #FFFFFF;"
            " font-weight: 600;"
            "}"
        )
        self.edit_toggle.toggled.connect(self._on_edit_toggled)
        top_row.addWidget(self.edit_toggle, 1)

        self.clear_button = QPushButton("Clear Board")
        self.clear_button.setMinimumHeight(34)
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self._on_clear_board)
        top_row.addWidget(self.clear_button)
        layout.addLayout(top_row)

        hint = QLabel(
            "Pick a piece, then click a square to place it. "
            "Right-click any square to remove a piece. "
            "Drag existing pieces to move them freely. "
            "\u2194 enables drag-only mode; \u232B erases."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.palette = PiecePalette()
        self.palette.pieceSelected.connect(self._on_palette_selected)
        layout.addWidget(self.palette)

        self._edit_group = group
        self._set_palette_enabled(False)
        return group

    # ------------------------------------------------------------------
    def _build_engine_group(self) -> QGroupBox:
        group = QGroupBox("Engine Strength")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        layout.setColumnStretch(1, 1)

        layout.addWidget(QLabel("Depth"), 0, 0)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(4, 40)
        self.depth_spin.setValue(int(self._config.get("analysis_depth", 14) or 14))
        layout.addWidget(self.depth_spin, 0, 1)

        layout.addWidget(QLabel("Thinking Time"), 1, 0)
        self.time_combo = QComboBox()
        self.time_combo.addItems(list(THINKING_TIMES.keys()))
        layout.addWidget(self.time_combo, 1, 1)

        layout.addWidget(QLabel("MultiPV"), 2, 0)
        self.multipv_spin = QSpinBox()
        self.multipv_spin.setRange(1, 10)
        self.multipv_spin.setValue(int(self._config.get("analysis_multipv", 1) or 1))
        layout.addWidget(self.multipv_spin, 2, 1)

        row = QHBoxLayout()
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setObjectName("Primary")
        self.analyze_button.setMinimumHeight(38)
        self.analyze_button.clicked.connect(self.analyze)
        row.addWidget(self.analyze_button)

        self.stop_button = QPushButton("Stop Analysis")
        self.stop_button.setObjectName("Danger")
        self.stop_button.setMinimumHeight(38)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.cancel_analysis)
        row.addWidget(self.stop_button)

        layout.addLayout(row, 3, 0, 1, 2)
        return group

    # ------------------------------------------------------------------
    def refresh_settings(self) -> None:
        self.board_widget.set_theme(str(self._config.get("board_theme", "Green")))
        self.board_widget.set_piece_set(str(self._config.get("piece_set", "Glyphs")))

    # ------------------------------------------------------------------
    # edit mode plumbing
    # ------------------------------------------------------------------
    def _set_palette_enabled(self, enabled: bool) -> None:
        for btn in self.palette._buttons.values():
            btn.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)

    def _on_edit_toggled(self, checked: bool) -> None:
        self.cancel_analysis()
        self.board_widget.set_edit_mode(bool(checked))
        self._set_palette_enabled(bool(checked))
        if checked:
            self.status_label.setText(
                "Edit mode: place, move or remove any piece. "
                "When you are done, uncheck Edit Position and press Analyze."
            )
        else:
            # Validate the position before leaving edit mode.
            valid, message = self._position_is_analyzable()
            if not valid:
                dialogs.error(
                    self,
                    "Position Not Valid",
                    "The current position cannot be analysed:\n\n"
                    + message
                    + "\n\nFix the position and try again.",
                )
                self.edit_toggle.blockSignals(True)
                self.edit_toggle.setChecked(True)
                self.edit_toggle.blockSignals(False)
                self.board_widget.set_edit_mode(True)
                self._set_palette_enabled(True)
                return
            self.status_label.setText("Position ready. Press Analyze.")

    def _on_palette_selected(self, value) -> None:
        # Auto-enable edit mode when the user picks a palette entry.
        if not self.edit_toggle.isChecked():
            self.edit_toggle.setChecked(True)
            return  # the toggled() slot will enable edit mode

        if value is None:
            self.board_widget.clear_palette()
        elif value == "eraser":
            self.board_widget.set_palette_eraser(True)
        else:
            piece_type, color = value
            self.board_widget.set_palette_piece(piece_type, color)

    def _on_clear_board(self) -> None:
        if not self.board_widget.is_edit_mode():
            return
        self._board.clear()
        self.board_widget.update()
        self._on_board_edited()
        self.status_label.setText("Board cleared. Place the pieces you want.")

    # ------------------------------------------------------------------
    def _on_board_edited(self) -> None:
        # Auto-update the FEN text field.
        try:
            self.fen_edit.setText(self._board.fen())
        except Exception:
            pass
        if self.board_widget.is_edit_mode():
            self.status_label.setText("Position edited. Uncheck Edit Position to analyse.")

    # ------------------------------------------------------------------
    def _position_is_analyzable(self) -> tuple[bool, str]:
        board = self._board
        if board.king(chess.WHITE) is None:
            return False, "The position has no white king."
        if board.king(chess.BLACK) is None:
            return False, "The position has no black king."

        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None:
                continue
            if piece.piece_type == chess.PAWN and chess.square_rank(square) in (0, 7):
                return False, "Pawns cannot stand on the first or last rank."

        # Basic legality: the side NOT to move must not be in check.
        try:
            checkers = board.checkers()
        except Exception:
            checkers = None
        return True, ""

    # ------------------------------------------------------------------
    def _sync_board(self) -> None:
        self.board_widget.set_board(self._board)
        self.board_widget.clear_arrows()
        self.fen_edit.setText(self._board.fen())
        self.side_combo.blockSignals(True)
        self.side_combo.setCurrentText("White" if self._board.turn == chess.WHITE else "Black")
        self.side_combo.blockSignals(False)

    def _on_board_move(self, move: chess.Move) -> None:
        if self.board_widget.is_edit_mode():
            return
        board_before = self._board.copy(stack=False)
        if move not in self._board.legal_moves:
            return
        self._board.push(move)
        self._sounds.play_for_move(board_before, move, self._board)
        self._sync_board()
        self.status_label.setText("Position updated.")

    def _on_side_changed(self, value: str) -> None:
        fen = set_side_to_move(self._board.fen(), value == "White")
        try:
            self._board = chess.Board(fen)
        except ValueError:
            return
        self.board_widget.set_board(self._board)
        self.fen_edit.setText(self._board.fen())

    # ------------------------------------------------------------------
    def load_fen(self) -> None:
        fen = self.fen_edit.text().strip()
        valid, message = validate_fen(fen)
        if not valid:
            dialogs.error(
                self,
                "Invalid FEN",
                "The position could not be loaded.\n"
                "Please check the FEN and try again.\n\n" + message,
            )
            return
        self._board = chess.Board(fen)
        self._sync_board()
        self.status_label.setText("Position loaded.")

    def copy_fen(self) -> None:
        QApplication.clipboard().setText(self._board.fen())
        self.status_label.setText("FEN copied to the clipboard.")

    def reset_position(self) -> None:
        self.cancel_analysis()
        self._board = chess.Board()
        self._sync_board()
        self.results_table.setRowCount(0)
        self.status_label.setText("Position reset to the starting position.")

    def flip_board(self) -> None:
        self.board_widget.flip()

    # ------------------------------------------------------------------
    def analyze(self) -> None:
        if not self._engine_manager.is_available():
            dialogs.error(
                self,
                "Stockfish Engine Not Found",
                "Stockfish Engine Not Found\n\n"
                "Please install Stockfish and select stockfish.exe from Settings.",
            )
            return

        valid, message = self._position_is_analyzable()
        if not valid:
            dialogs.error(
                self,
                "Position Not Valid",
                "The current position cannot be analysed:\n\n"
                + message
                + "\n\nFix the position and try again.",
            )
            return

        self.cancel_analysis()

        depth = self.depth_spin.value()
        movetime = THINKING_TIMES.get(self.time_combo.currentText())
        multipv = self.multipv_spin.value()

        try:
            task = self._engine_manager.create_task(
                fen=self._board.fen(),
                depth=depth,
                movetime=movetime,
                multipv=multipv,
            )
        except Exception as exc:
            dialogs.error(self, "Engine Error", str(exc))
            return

        self._task = task
        self._lines = []
        self.results_table.setRowCount(0)
        self.analyze_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Analyzing...")

        task.infoReady.connect(self._on_info)
        task.finishedOk.connect(self._on_finished)
        task.failed.connect(self._on_failed)
        task.finished.connect(lambda: self.stop_button.setEnabled(False))
        task.start()

    def cancel_analysis(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task.wait(3000)
            self._task = None
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    # ------------------------------------------------------------------
    def _on_info(self, info) -> None:
        self.info_label.setText(
            f"Depth: {info.depth}   Nodes: {human_int(info.nodes)}   NPS: {human_int(info.nps)}"
        )
        self._upsert_line(info)

    def _upsert_line(self, info) -> None:
        index = max(0, info.multipv - 1)
        while self.results_table.rowCount() <= index:
            self.results_table.insertRow(self.results_table.rowCount())

        sans = pv_to_san(self._board, info.pv)
        move_san = sans[0] if sans else (info.pv[0] if info.pv else "-")
        pv_text = " ".join(sans) if sans else "-"

        values = [str(info.multipv), move_san, info.eval_text(), pv_text]
        for column, text in enumerate(values):
            item = QTableWidgetItem(text)
            if column in (0, 2):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(index, column, item)

    def _on_finished(self, outcome) -> None:
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._task = None

        if outcome.cancelled:
            self.status_label.setText("Analysis stopped.")
            return

        self.results_table.setRowCount(0)
        for info in outcome.lines:
            self._upsert_line(info)

        if outcome.bestmove:
            self.status_label.setText(
                f"Best move: {outcome.bestmove}   (Depth {outcome.lines[-1].depth if outcome.lines else '-'})"
            )
        else:
            self.status_label.setText("No legal move is available in this position.")

    def _on_failed(self, message: str) -> None:
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._task = None
        self.status_label.setText("Analysis failed.")
        dialogs.error(self, "Engine Error", message)

    # ------------------------------------------------------------------
    def _on_line_selected(self) -> None:
        rows = self.results_table.selectionModel().selectedRows()
        if not rows:
            self.board_widget.clear_arrows()
            return
        row = rows[0].row()
        if row >= self.results_table.rowCount():
            return
        item = self.results_table.item(row, 3)
        if item is None:
            return
        sans = item.text().split()
        board = self._board.copy()
        arrows = []
        uci_first = None
        for san in sans[:6]:
            try:
                move = board.parse_san(san)
            except ValueError:
                break
            if uci_first is None:
                uci_first = move
            board.push(move)

        if uci_first is not None:
            arrows = [(uci_first.from_square, uci_first.to_square, "#3FA96B")]
        self.board_widget.set_arrows(arrows)

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        self.cancel_analysis()