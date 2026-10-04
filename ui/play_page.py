"""Play a full game against Stockfish."""
from __future__ import annotations

import random
from typing import Optional

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.sounds import SoundManager
from app.utils import format_eval, human_int
from core.game import GameController
from core.pgn import build_game, export_pgn
from engine.engine_manager import EngineManager, EngineTask
from ui import dialogs
from ui.chess_board import ChessBoardWidget
from ui.evaluation_bar import EvaluationBar
from ui.move_list import MoveListWidget

DIFFICULTY_PRESETS = {
    "Beginner": {"depth": 8, "skill": 3},
    "Easy": {"depth": 11, "skill": 6},
    "Medium": {"depth": 15, "skill": 10},
    "Hard": {"depth": 18, "skill": 14},
    "Expert": {"depth": 23, "skill": 18},
    "Maximum": {"depth": 30, "skill": 20},
    "Custom": {"depth": None, "skill": None},
}

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
    "Custom": None,
}

COLOR_CHOICES = ["White", "Black", "Random"]


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


class PlayPage(QWidget):
    """Human vs Stockfish."""

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

        self._game = GameController()
        self._player_color = chess.WHITE
        self._engine_color = chess.BLACK
        self._game_active = False
        self._task: Optional[EngineTask] = None
        self._thinking = False

        self._build_ui()
        self._apply_settings()
        self._refresh_board()
        self._update_controls()

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
        self.board_widget.set_promotion_callback(self._ask_promotion)
        self.board_widget.moveRequested.connect(self._on_player_move)
        board_row.addWidget(self.board_widget, 1)

        board_column.addLayout(board_row, 1)

        self.status_label = QLabel("Configure the game and press Start Game.")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        board_column.addWidget(self.status_label)

        self._splitter.addWidget(board_container)

        # ---------------- Right: control panel (scrollable) -----------
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 4, 6, 4)
        panel_layout.setSpacing(12)

        panel_layout.addWidget(self._build_config_group())
        panel_layout.addWidget(self._build_status_group())
        panel_layout.addWidget(self._build_controls_group())

        move_frame = QGroupBox("Move History")
        move_layout = QVBoxLayout(move_frame)
        self.move_list = MoveListWidget()
        self.move_list.setMinimumHeight(180)
        move_layout.addWidget(self.move_list)
        panel_layout.addWidget(move_frame, 1)

        self._splitter.addWidget(_scrolled(panel, min_width=360, max_width=540))

        self._splitter.setStretchFactor(0, 5)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes([900, 460])

    # ------------------------------------------------------------------
    def _build_config_group(self) -> QGroupBox:
        group = QGroupBox("Game Setup")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        layout.setColumnStretch(1, 1)

        layout.addWidget(QLabel("Choose Your Color"), 0, 0)
        self.color_combo = QComboBox()
        self.color_combo.addItems(COLOR_CHOICES)
        layout.addWidget(self.color_combo, 0, 1)

        layout.addWidget(QLabel("Difficulty"), 1, 0)
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(list(DIFFICULTY_PRESETS.keys()))
        self.difficulty_combo.currentTextChanged.connect(self._on_difficulty_changed)
        layout.addWidget(self.difficulty_combo, 1, 1)

        layout.addWidget(QLabel("Thinking Time"), 2, 0)
        self.time_combo = QComboBox()
        self.time_combo.addItems(list(THINKING_TIMES.keys()))
        self.time_combo.currentTextChanged.connect(self._on_time_changed)
        layout.addWidget(self.time_combo, 2, 1)

        layout.addWidget(QLabel("Engine Depth"), 3, 0)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(4, 40)
        self.depth_spin.setValue(15)
        layout.addWidget(self.depth_spin, 3, 1)

        layout.addWidget(QLabel("Custom Time (s)"), 4, 0)
        self.custom_time_spin = QSpinBox()
        self.custom_time_spin.setRange(1, 600)
        self.custom_time_spin.setValue(5)
        self.custom_time_spin.setEnabled(False)
        layout.addWidget(self.custom_time_spin, 4, 1)

        self.start_button = QPushButton("Start Game")
        self.start_button.setObjectName("Primary")
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self.start_game)
        layout.addWidget(self.start_button, 5, 0, 1, 2)

        return group

    # ------------------------------------------------------------------
    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Engine Status")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.thinking_label = QLabel("Idle")
        self.thinking_label.setObjectName("H3")
        layout.addWidget(self.thinking_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)

        self.depth_value = QLabel("-")
        self.nodes_value = QLabel("-")
        self.nps_value = QLabel("-")
        self.eval_value = QLabel("-")

        for row, (caption, widget) in enumerate(
            (
                ("Depth", self.depth_value),
                ("Nodes", self.nodes_value),
                ("NPS", self.nps_value),
                ("Evaluation", self.eval_value),
            )
        ):
            label = QLabel(caption)
            label.setObjectName("Muted")
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.stop_button = QPushButton("Stop Analysis")
        self.stop_button.setObjectName("Danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._cancel_engine)
        layout.addWidget(self.stop_button)

        return group

    # ------------------------------------------------------------------
    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Game Controls")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        buttons = [
            ("New Game", self.new_game),
            ("Reset", self.reset_game),
            ("Undo", self.undo_move),
            ("Redo", self.redo_move),
            ("Flip Board", self.flip_board),
            ("Load FEN", self.load_fen),
            ("Copy FEN", self.copy_fen),
            ("Export PGN", self.export_pgn),
        ]

        for index, (label, handler) in enumerate(buttons):
            button = QPushButton(label)
            button.setMinimumHeight(32)
            button.clicked.connect(handler)
            layout.addWidget(button, index // 2, index % 2)

        self.undo_button = layout.itemAtPosition(1, 0).widget()
        self.redo_button = layout.itemAtPosition(1, 1).widget()

        return group

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    def _apply_settings(self) -> None:
        self.board_widget.set_theme(str(self._config.get("board_theme", "Green")))
        self.board_widget.set_piece_set(str(self._config.get("piece_set", "Glyphs")))

        self.color_combo.setCurrentText(str(self._config.get("player_color", "White")))
        difficulty = str(self._config.get("difficulty", "Medium"))
        if difficulty in DIFFICULTY_PRESETS:
            self.difficulty_combo.setCurrentText(difficulty)
        thinking = str(self._config.get("thinking_time", "Unlimited"))
        if thinking in THINKING_TIMES:
            self.time_combo.setCurrentText(thinking)
        self.depth_spin.setValue(int(self._config.get("engine_depth", 15) or 15))

    def refresh_settings(self) -> None:
        self.board_widget.set_theme(str(self._config.get("board_theme", "Green")))
        self.board_widget.set_piece_set(str(self._config.get("piece_set", "Glyphs")))

    # ------------------------------------------------------------------
    def _on_difficulty_changed(self, name: str) -> None:
        preset = DIFFICULTY_PRESETS.get(name, {})
        depth = preset.get("depth")
        if depth:
            self.depth_spin.setValue(int(depth))

    def _on_time_changed(self, name: str) -> None:
        self.custom_time_spin.setEnabled(name == "Custom")

    # ------------------------------------------------------------------
    def _current_movetime(self) -> Optional[float]:
        name = self.time_combo.currentText()
        if name == "Custom":
            return float(self.custom_time_spin.value())
        return THINKING_TIMES.get(name)

    def _current_skill(self) -> Optional[int]:
        preset = DIFFICULTY_PRESETS.get(self.difficulty_combo.currentText(), {})
        return preset.get("skill")

    # ------------------------------------------------------------------
    # game flow
    # ------------------------------------------------------------------
    def start_game(self) -> None:
        if not self._engine_manager.is_available():
            self._show_engine_missing()
            return

        choice = self.color_combo.currentText()
        if choice == "Random":
            self._player_color = random.choice([chess.WHITE, chess.BLACK])
        else:
            self._player_color = chess.WHITE if choice == "White" else chess.BLACK
        self._engine_color = not self._player_color

        self._config.update(
            {
                "player_color": choice,
                "difficulty": self.difficulty_combo.currentText(),
                "thinking_time": self.time_combo.currentText(),
                "engine_depth": self.depth_spin.value(),
            }
        )
        self._config.save()

        self._game.reset()
        self._game_active = True
        self.board_widget.set_interactive(True)
        self.board_widget.set_orientation(self._player_color)
        self.eval_bar.set_flipped(self._player_color == chess.BLACK)
        self._refresh_board()
        self.move_list.set_moves([])
        self._reset_engine_status()

        color_name = "White" if self._player_color == chess.WHITE else "Black"
        self.status_label.setText(f"Game started \u2014 you play {color_name}.")

        if self._game.board.turn == self._engine_color:
            self._engine_move()

    def new_game(self) -> None:
        self._cancel_engine()
        self.start_game()

    def reset_game(self) -> None:
        self._cancel_engine()
        self._game.reset()
        self._game_active = False
        self.board_widget.set_last_move(None)
        self.board_widget.clear_arrows()
        self._refresh_board()
        self.move_list.set_moves([])
        self._reset_engine_status()
        self.status_label.setText("Position reset. Press Start Game to play.")
        self._update_controls()

    def undo_move(self) -> None:
        if not self._game_active:
            return
        if self._game.can_undo:
            self._game.undo()
            if self._game.can_undo and self._game.board.turn == self._engine_color:
                self._game.undo()
            self._refresh_board()
            self._update_move_list()

    def redo_move(self) -> None:
        if not self._game_active:
            return
        if self._game.can_redo:
            self._game.redo()
            if self._game.can_redo and self._game.board.turn == self._player_color:
                self._game.redo()
            self._refresh_board()
            self._update_move_list()

    def flip_board(self) -> None:
        self.board_widget.flip()
        self.eval_bar.set_flipped(self.board_widget.orientation() == chess.BLACK)

    # ------------------------------------------------------------------
    def load_fen(self) -> None:
        dialog = dialogs.FenDialog(self._game.fen(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        fen = dialog.fen() or ""
        valid, message = self._validate_fen(fen)
        if not valid:
            dialogs.error(
                self,
                "Invalid FEN",
                "The position could not be loaded.\nPlease check the FEN and try again.\n\n" + message,
            )
            return
        self._cancel_engine()
        self._game.reset(fen)
        self._game_active = False
        self._refresh_board()
        self.move_list.set_moves([])
        self.status_label.setText("Position loaded from FEN.")

    def copy_fen(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._game.fen())
        self.status_label.setText("FEN copied to the clipboard.")

    def export_pgn(self) -> None:
        moves = self._game.move_history()
        if not moves:
            dialogs.info(self, "Export PGN", "There are no moves to export yet.")
            return

        white_name = "Player" if self._player_color == chess.WHITE else "Stockfish"
        black_name = "Player" if self._player_color == chess.BLACK else "Stockfish"
        game = build_game(
            moves,
            start_fen=self._game.start_fen,
            white=white_name,
            black=black_name,
        )

        path, _ = QFileDialog.getSaveFileName(
            self, "Export PGN", "game.pgn", "Portable Game Notation (*.pgn)"
        )
        if not path:
            return
        try:
            export_pgn(game, path)
        except OSError as exc:
            dialogs.error(self, "Export Failed", f"The PGN file could not be written.\n\n{exc}")
            return
        self.status_label.setText(f"Game exported to {path}")

    # ------------------------------------------------------------------
    def _validate_fen(self, fen: str) -> tuple[bool, str]:
        from core.fen import validate_fen

        return validate_fen(fen)

    # ------------------------------------------------------------------
    def _ask_promotion(self, from_square: int, to_square: int) -> Optional[int]:
        return dialogs.ask_promotion(self, self._game.board.turn)

    # ------------------------------------------------------------------
    def _on_player_move(self, move: chess.Move) -> None:
        if not self._game_active or self._thinking:
            return
        if self._game.board.turn != self._player_color:
            return

        board_before = self._game.board.copy(stack=False)
        if not self._game.push(move):
            return

        self._sounds.play_for_move(
            board_before, move, self._game.board, perspective=self._player_color
        )

        self._refresh_board()
        self._update_move_list()

        if self._check_game_over():
            return

        self._engine_move()

    # ------------------------------------------------------------------
    def _engine_move(self) -> None:
        if not self._game_active:
            return

        try:
            task = self._engine_manager.create_task(
                fen=self._game.start_fen,
                moves=[m.uci() for m in self._game.board.move_stack],
                depth=self.depth_spin.value(),
                movetime=self._current_movetime(),
                multipv=1,
                skill=self._current_skill(),
            )
        except Exception as exc:
            dialogs.error(
                self,
                "Stockfish Engine Not Found",
                f"{exc}\n\nPlease select stockfish.exe from Settings.",
            )
            self._game_active = False
            return

        self._task = task
        self._thinking = True
        self.thinking_label.setText("Stockfish is thinking...")
        self.stop_button.setEnabled(True)
        self.board_widget.set_interactive(False)

        task.infoReady.connect(self._on_engine_info)
        task.finishedOk.connect(self._on_engine_finished)
        task.failed.connect(self._on_engine_failed)
        task.finished.connect(self._on_task_closed)
        task.start()

    # ------------------------------------------------------------------
    def _on_engine_info(self, info) -> None:
        self.depth_value.setText(str(info.depth))
        self.nodes_value.setText(human_int(info.nodes))
        self.nps_value.setText(human_int(info.nps))
        self.eval_value.setText(info.eval_text())
        self.eval_bar.set_score(info.score_cp, info.score_mate)

    def _on_engine_finished(self, outcome) -> None:
        self._thinking = False
        self.stop_button.setEnabled(False)
        self.board_widget.set_interactive(True)
        self.thinking_label.setText("Idle")

        if outcome.lines:
            last = outcome.lines[0]
            self.depth_value.setText(str(last.depth))
            self.nodes_value.setText(human_int(last.nodes))
            self.nps_value.setText(human_int(last.nps))
            self.eval_value.setText(last.eval_text())
            self.eval_bar.set_score(last.score_cp, last.score_mate)

        if not self._game_active:
            return

        if not outcome.bestmove:
            self._check_game_over()
            return

        try:
            move = chess.Move.from_uci(outcome.bestmove)
        except ValueError:
            self.status_label.setText("The engine proposed an invalid move; the game was stopped.")
            self._game_active = False
            return

        if move not in self._game.board.legal_moves:
            promoted = chess.Move.from_uci(outcome.bestmove + "q")
            if promoted in self._game.board.legal_moves:
                move = promoted
            else:
                self.status_label.setText("The engine proposed an illegal move; the game was stopped.")
                self._game_active = False
                return

        board_before = self._game.board.copy(stack=False)
        if not self._game.push(move):
            self.status_label.setText("The engine's move could not be applied.")
            self._game_active = False
            return

        self._sounds.play_for_move(
            board_before, move, self._game.board, perspective=self._player_color
        )

        self._refresh_board()
        self._update_move_list()

        if self._check_game_over():
            return

        if self._game.board.turn == self._player_color:
            self.status_label.setText("Your turn.")
        else:
            self._engine_move()

    def _on_engine_failed(self, message: str) -> None:
        self._thinking = False
        self.stop_button.setEnabled(False)
        self.board_widget.set_interactive(True)
        self.thinking_label.setText("Engine error")
        dialogs.error(self, "Engine Error", message)

    def _on_task_closed(self) -> None:
        self._task = None

    def _cancel_engine(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task.wait(3000)
            self._task = None
        self._thinking = False
        self.stop_button.setEnabled(False)
        self.board_widget.set_interactive(True)
        self.thinking_label.setText("Idle")

    # ------------------------------------------------------------------
    def _check_game_over(self) -> bool:
        board = self._game.board
        if board.is_checkmate():
            winner = "Black" if board.turn == chess.WHITE else "White"
            self.status_label.setText(f"Checkmate! {winner} wins.")
            self._end_game()
            return True
        if board.is_stalemate():
            self.status_label.setText("Stalemate \u2014 the game is a draw.")
            self._end_game()
            return True
        if board.is_insufficient_material():
            self.status_label.setText("Draw by insufficient material.")
            self._end_game()
            return True
        if board.is_seventyfive_moves():
            self.status_label.setText("Draw by the seventy-five move rule.")
            self._end_game()
            return True
        if board.is_fivefold_repetition():
            self.status_label.setText("Draw by fivefold repetition.")
            self._end_game()
            return True
        return False

    def _end_game(self) -> None:
        self._game_active = False
        self.board_widget.set_interactive(False)
        self._update_controls()

    # ------------------------------------------------------------------
    def _refresh_board(self) -> None:
        self.board_widget.set_board(self._game.board)
        last_move = self._game.board.peek() if self._game.board.move_stack else None
        self.board_widget.set_last_move(last_move)
        self._update_controls()

    def _update_move_list(self) -> None:
        board = chess.Board(self._game.start_fen)
        sans = []
        for move in self._game.board.move_stack:
            if move not in board.legal_moves:
                break
            sans.append(board.san(move))
            board.push(move)
        self.move_list.set_moves(sans)
        if sans:
            self.move_list.set_current_ply(len(sans) - 1)

    def _update_controls(self) -> None:
        if hasattr(self, "undo_button"):
            self.undo_button.setEnabled(self._game_active and self._game.can_undo)
            self.redo_button.setEnabled(self._game_active and self._game.can_redo)

    def _reset_engine_status(self) -> None:
        self.depth_value.setText("-")
        self.nodes_value.setText("-")
        self.nps_value.setText("-")
        self.eval_value.setText("-")
        self.eval_bar.set_score(0, None)
        self.thinking_label.setText("Idle")

    # ------------------------------------------------------------------
    def _show_engine_missing(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Stockfish Engine Not Found")
        box.setText(
            "Stockfish Engine Not Found\n\n"
            "Please install Stockfish and select stockfish.exe from Settings."
        )
        open_settings = box.addButton("Open Settings", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_settings:
            self.requestNavigate.emit("settings")

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        self._cancel_engine()