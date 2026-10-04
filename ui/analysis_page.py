"""Full game analysis with an evaluation graph and move classification."""
from __future__ import annotations

from typing import List, Optional

import chess
import chess.pgn
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.sounds import SoundManager
from app.theme import CLASSIFICATION_COLORS
from core.evaluation import eval_to_plot
from core.pgn import PgnError, read_pgn
from engine.analysis import GameAnalyzer, GameAnalysisResult, build_boards, pv_to_san
from engine.engine_manager import EngineManager
from ui import dialogs
from ui.chess_board import ChessBoardWidget
from ui.evaluation_bar import EvaluationBar
from ui.evaluation_graph import EvaluationGraph
from ui.move_list import MoveListWidget


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


class AnalysisPage(QWidget):
    """Import a PGN, analyse it and browse the results."""

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

        self._game: Optional[chess.pgn.Game] = None
        self._boards: List[chess.Board] = []
        self._result: Optional[GameAnalysisResult] = None
        self._analyzer: Optional[GameAnalyzer] = None
        self._current_ply = -1

        self._build_ui()
        self.refresh_settings()
        self._update_navigation()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(10)
        outer.addWidget(self._splitter)

        # ---------------- Left: board column --------------------------
        board_container = QWidget()
        board_column = QVBoxLayout(board_container)
        board_column.setContentsMargins(4, 4, 4, 4)
        board_column.setSpacing(10)

        board_row = QHBoxLayout()
        board_row.setSpacing(10)

        self.eval_bar = EvaluationBar()
        board_row.addWidget(self.eval_bar)

        self.board_widget = ChessBoardWidget()
        self.board_widget.set_interactive(False)
        board_row.addWidget(self.board_widget, 1)

        board_column.addLayout(board_row, 1)

        nav_row = QHBoxLayout()
        self.first_button = QPushButton("\u23EE First")
        self.first_button.clicked.connect(self.go_first)
        self.prev_button = QPushButton("\u25C0 Previous")
        self.prev_button.clicked.connect(self.go_previous)
        self.next_button = QPushButton("Next \u25B6")
        self.next_button.clicked.connect(self.go_next)
        self.last_button = QPushButton("Last \u23ED")
        self.last_button.clicked.connect(self.go_last)
        for button in (self.first_button, self.prev_button, self.next_button, self.last_button):
            button.setMinimumHeight(32)
            nav_row.addWidget(button)
        board_column.addLayout(nav_row)

        self.details_frame = QFrame()
        self.details_frame.setObjectName("CardFlat")
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(14, 12, 14, 12)
        details_layout.setSpacing(6)

        self.details_title = QLabel("Move Details")
        self.details_title.setObjectName("SectionTitle")
        details_layout.addWidget(self.details_title)

        self.details_label = QLabel("No move selected.")
        self.details_label.setWordWrap(True)
        self.details_label.setTextFormat(Qt.TextFormat.RichText)
        details_layout.addWidget(self.details_label)

        board_column.addWidget(self.details_frame)

        self._splitter.addWidget(board_container)

        # ---------------- Right: panel (scrollable) -------------------
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 4, 6, 4)
        panel_layout.setSpacing(12)

        panel_layout.addWidget(self._build_import_group())

        self.graph = EvaluationGraph()
        self.graph.moveSelected.connect(self.set_ply)
        self.graph.setMinimumHeight(180)

        graph_frame = QGroupBox("Evaluation Graph")
        graph_layout = QVBoxLayout(graph_frame)
        graph_layout.setContentsMargins(8, 8, 8, 8)
        graph_layout.addWidget(self.graph)
        panel_layout.addWidget(graph_frame, 2)

        moves_frame = QGroupBox("Move History")
        moves_layout = QVBoxLayout(moves_frame)
        self.move_list = MoveListWidget()
        self.move_list.setMinimumHeight(200)
        self.move_list.moveActivated.connect(self.set_ply)
        moves_layout.addWidget(self.move_list)
        panel_layout.addWidget(moves_frame, 3)

        self._splitter.addWidget(_scrolled(panel, min_width=420, max_width=620))
        self._splitter.setStretchFactor(0, 5)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setSizes([860, 540])

    # ------------------------------------------------------------------
    def _build_import_group(self) -> QGroupBox:
        group = QGroupBox("Game Analysis")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        row = QHBoxLayout()
        import_button = QPushButton("Import PGN")
        import_button.setMinimumHeight(32)
        import_button.clicked.connect(self.import_pgn)
        row.addWidget(import_button)

        paste_button = QPushButton("Paste PGN")
        paste_button.setMinimumHeight(32)
        paste_button.clicked.connect(self.paste_pgn)
        row.addWidget(paste_button)
        layout.addLayout(row)

        settings_row = QGridLayout()
        settings_row.setColumnStretch(1, 1)
        settings_row.addWidget(QLabel("Analysis Depth"), 0, 0)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(4, 30)
        self.depth_spin.setValue(int(self._config.get("analysis_depth", 14) or 14))
        settings_row.addWidget(self.depth_spin, 0, 1)
        layout.addLayout(settings_row)

        buttons_row = QHBoxLayout()
        self.analyze_button = QPushButton("Analyze Game")
        self.analyze_button.setObjectName("Primary")
        self.analyze_button.setMinimumHeight(38)
        self.analyze_button.clicked.connect(self.analyze_game)
        buttons_row.addWidget(self.analyze_button)

        self.stop_button = QPushButton("Stop Analysis")
        self.stop_button.setObjectName("Danger")
        self.stop_button.setMinimumHeight(38)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.cancel_analysis)
        buttons_row.addWidget(self.stop_button)
        layout.addLayout(buttons_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.summary_button = QPushButton("Show Game Summary")
        self.summary_button.setMinimumHeight(32)
        self.summary_button.setEnabled(False)
        self.summary_button.clicked.connect(self.show_summary)
        layout.addWidget(self.summary_button)

        self.status_label = QLabel("Import or paste a PGN to begin.")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        return group

    # ------------------------------------------------------------------
    def refresh_settings(self) -> None:
        self.board_widget.set_theme(str(self._config.get("board_theme", "Green")))
        self.board_widget.set_piece_set(str(self._config.get("piece_set", "Glyphs")))

    # ------------------------------------------------------------------
    # PGN loading
    # ------------------------------------------------------------------
    def import_pgn(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import PGN", "", "Portable Game Notation (*.pgn);;All Files (*)"
        )
        if not path:
            return
        try:
            text = open(path, "r", encoding="utf-8", errors="replace").read()
        except OSError as exc:
            dialogs.error(self, "Import Failed", f"The file could not be read.\n\n{exc}")
            return
        self._load_pgn_text(text)

    def paste_pgn(self) -> None:
        dialog = dialogs.PgnDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._load_pgn_text(dialog.pgn() or "")

    def _load_pgn_text(self, text: str) -> None:
        try:
            game, warnings = read_pgn(text)
        except PgnError as exc:
            dialogs.error(
                self,
                "Invalid PGN",
                "The game could not be loaded.\nPlease check the PGN and try again.\n\n" + str(exc),
            )
            return

        self.cancel_analysis()
        self._game = game
        self._boards = build_boards(game)
        self._result = None
        self._current_ply = -1

        move_count = max(0, len(self._boards) - 1)
        self.progress.setValue(0)
        self.summary_button.setEnabled(False)
        self.graph.clear()

        white = game.headers.get("White", "?")
        black = game.headers.get("Black", "?")
        self.status_label.setText(
            f"Loaded {white} vs {black} \u2014 {move_count} moves. Press Analyze Game."
        )
        if warnings:
            dialogs.warn(self, "PGN Warnings", "\n".join(warnings))

        self._sync_view()
        self._update_navigation()

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------
    def analyze_game(self) -> None:
        if not self._boards or len(self._boards) < 2:
            dialogs.info(self, "Game Analysis", "Please import a PGN with at least one move first.")
            return
        if not self._engine_manager.is_available():
            dialogs.error(
                self,
                "Stockfish Engine Not Found",
                "Stockfish Engine Not Found\n\n"
                "Please install Stockfish and select stockfish.exe from Settings.",
            )
            return

        self.cancel_analysis()

        try:
            engine = self._engine_manager.ensure_engine()
        except Exception as exc:
            dialogs.error(self, "Engine Error", str(exc))
            return

        depth = self.depth_spin.value()
        self._config.set("analysis_depth", depth)
        self._config.save()

        analyzer = GameAnalyzer(engine, self._boards, depth=depth, parent=self)
        self._analyzer = analyzer
        analyzer.progress.connect(self._on_progress)
        analyzer.partialResult.connect(self._on_partial)
        analyzer.analysisFinished.connect(self._on_analysis_finished)
        analyzer.failed.connect(self._on_analysis_failed)
        analyzer.finished.connect(lambda: self.stop_button.setEnabled(False))

        self.analyze_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.summary_button.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText("Analyzing game...")
        analyzer.start()

    def cancel_analysis(self) -> None:
        if self._analyzer is not None:
            self._analyzer.cancel()
            self._analyzer.wait(5000)
            self._analyzer = None
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    # ------------------------------------------------------------------
    def _on_progress(self, done: int, total: int) -> None:
        value = int(done / max(1, total) * 100)
        self.progress.setValue(value)

    def _on_partial(self, report) -> None:
        self.status_label.setText(
            f"Analyzing... {report.ply + 1} moves classified"
        )

    def _on_analysis_finished(self, result: GameAnalysisResult) -> None:
        self._analyzer = None
        self._result = result
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress.setValue(100 if result.complete else self.progress.value())
        self.summary_button.setEnabled(True)

        self._refresh_move_list()
        self._refresh_graph()

        label = "Analysis complete" if result.complete else "Analysis stopped early"
        self.status_label.setText(
            f"{label}. White accuracy {result.white.accuracy:.1f}% \u2014 "
            f"Black accuracy {result.black.accuracy:.1f}%."
        )

        if self._current_ply < 0 and self._boards:
            # Initial landing on the first move: don't play a sound here.
            self._current_ply = -1
            self.set_ply(0, silent=True)

    def _on_analysis_failed(self, message: str) -> None:
        self._analyzer = None
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Analysis failed.")
        dialogs.error(self, "Analysis Error", message)

    # ------------------------------------------------------------------
    # view helpers
    # ------------------------------------------------------------------
    def _refresh_move_list(self) -> None:
        if not self._game:
            return
        board = self._boards[0].copy()
        sans: List[str] = []
        classifications: List[str] = []
        for index, move in enumerate(self._game.mainline_moves()):
            if move not in board.legal_moves:
                break
            sans.append(board.san(move))
            if self._result and index < len(self._result.reports):
                classifications.append(self._result.reports[index].classification)
            else:
                classifications.append("")
            board.push(move)
        self.move_list.set_moves(sans, classifications)

    def _refresh_graph(self) -> None:
        if not self._result or not self._result.evals:
            self.graph.clear()
            return
        values = [
            eval_to_plot(cp, mate)
            for cp, mate in zip(self._result.evals, self._result.mates)
        ]
        labels = [report.classification for report in self._result.reports]
        self.graph.set_data(values, labels)

    # ------------------------------------------------------------------
    def set_ply(self, ply: int, silent: bool = False) -> None:
        if not self._boards:
            return
        previous = self._current_ply
        maximum = len(self._boards) - 2
        ply = max(0, min(maximum, ply))
        self._current_ply = ply
        self._sync_view()
        self._update_navigation()

        # Play a navigation sound when the user actually moves between plies.
        if not silent and previous >= 0 and ply != previous and 0 <= ply < len(self._boards) - 1:
            self._play_navigation_sound(ply)

    def _play_navigation_sound(self, ply: int) -> None:
        if ply < 0 or ply >= len(self._boards) - 1:
            return
        board_before = self._boards[ply]
        board_after = self._boards[ply + 1]
        if not board_after.move_stack:
            return
        move = board_after.peek()
        self._sounds.play_for_move(board_before, move, board_after)

    def go_first(self) -> None:
        if self._boards:
            self.set_ply(0)

    def go_last(self) -> None:
        if self._boards:
            self.set_ply(len(self._boards) - 2)

    def go_previous(self) -> None:
        if self._boards:
            self.set_ply(max(0, self._current_ply - 1))

    def go_next(self) -> None:
        if self._boards:
            self.set_ply(min(len(self._boards) - 2, self._current_ply + 1))

    # ------------------------------------------------------------------
    def _sync_view(self) -> None:
        if not self._boards:
            self.board_widget.set_board(chess.Board())
            self.board_widget.set_last_move(None)
            self.board_widget.clear_arrows()
            self.eval_bar.set_score(0, None)
            self.details_label.setText("No move selected.")
            return

        index = self._current_ply + 1
        index = max(0, min(len(self._boards) - 1, index))
        board = self._boards[index]
        self.board_widget.set_board(board)

        if index > 0 and board.move_stack:
            last_move = board.peek()
            self.board_widget.set_last_move(last_move)
        else:
            self.board_widget.set_last_move(None)

        self.move_list.set_current_ply(self._current_ply)
        self.graph.set_cursor(self._current_ply)
        self._update_details()
        self._update_arrows()

    def _update_arrows(self) -> None:
        if not self._result or self._current_ply < 0 or self._current_ply >= len(self._result.reports):
            self.board_widget.clear_arrows()
            return

        report = self._result.reports[self._current_ply]
        arrows = [(report.move.from_square, report.move.to_square, "#E0A33E")]
        if report.best_move_uci:
            try:
                best = chess.Move.from_uci(report.best_move_uci)
                arrows.append((best.from_square, best.to_square, "#3FA96B"))
            except ValueError:
                pass
        self.board_widget.set_arrows(arrows)

    def _update_details(self) -> None:
        if not self._result or self._current_ply < 0 or self._current_ply >= len(self._result.reports):
            self.details_label.setText("No move selected.")
            self.eval_bar.set_score(0, None)
            return

        report = self._result.reports[self._current_ply]
        color = CLASSIFICATION_COLORS.get(report.classification, "#8E9BA5")

        pv_text = " ".join(report.pv_san[:8]) if report.pv_san else "-"
        side = "White" if report.color == chess.WHITE else "Black"

        self.details_label.setText(
            f"<b>Move:</b> {report.san} &nbsp; <span style='color:#8E9BA5'>({side})</span><br>"
            f"<b>Classification:</b> <span style='color:{color}'>{report.classification}</span><br>"
            f"<b>Evaluation before:</b> {report.eval_before_text()}<br>"
            f"<b>Evaluation after:</b> {report.eval_after_text()}<br>"
            f"<b>Centipawn loss:</b> {report.cp_loss}<br>"
            f"<b>Engine best move:</b> {report.best_move_san or '-'}<br>"
            f"<b>Principal Variation:</b> {pv_text}"
        )

        self.eval_bar.set_score(report.eval_after, report.mate_after)

    # ------------------------------------------------------------------
    def _update_navigation(self) -> None:
        has_game = bool(self._boards) and len(self._boards) > 1
        for button in (
            getattr(self, "first_button", None),
            getattr(self, "prev_button", None),
            getattr(self, "next_button", None),
            getattr(self, "last_button", None),
        ):
            if button is not None:
                button.setEnabled(has_game)

    # ------------------------------------------------------------------
    def show_summary(self) -> None:
        if self._result is None:
            return
        dialog = dialogs.GameSummaryDialog(self._result, self)
        dialog.exec()

    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.go_previous()
        elif key == Qt.Key.Key_Right:
            self.go_next()
        elif key == Qt.Key.Key_Home:
            self.go_first()
        elif key == Qt.Key.Key_End:
            self.go_last()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        self.cancel_analysis()