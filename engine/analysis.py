"""Full-game analysis: evaluations, move classification and accuracy."""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

import chess
from PySide6.QtCore import QThread, Signal

from core.evaluation import (
    classify_move,
    move_accuracy,
    MATE_CP,
)
from engine.stockfish import EngineError, EngineInfo, StockfishEngine


# ----------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------
@dataclass
class MoveReport:
    """Everything we know about a single played move."""

    ply: int
    move: chess.Move
    san: str
    color: bool
    eval_before: Optional[int] = None
    eval_after: Optional[int] = None
    mate_before: Optional[int] = None
    mate_after: Optional[int] = None
    cp_loss: int = 0
    classification: str = "Good"
    accuracy: float = 100.0
    best_move_uci: str = ""
    best_move_san: str = ""
    pv_uci: List[str] = field(default_factory=list)
    pv_san: List[str] = field(default_factory=list)

    def eval_before_text(self) -> str:
        return _format_score(self.eval_before, self.mate_before)

    def eval_after_text(self) -> str:
        return _format_score(self.eval_after, self.mate_after)


def _format_score(cp: Optional[int], mate: Optional[int]) -> str:
    if mate is not None:
        if mate == 0:
            return "#"
        return f"M{abs(mate)}" if mate > 0 else f"-M{abs(mate)}"
    if cp is None:
        return "0.00"
    return f"{cp / 100.0:+.2f}"


@dataclass
class ColorSummary:
    best: int = 0
    excellent: int = 0
    good: int = 0
    inaccuracy: int = 0
    mistake: int = 0
    blunder: int = 0
    accuracy: float = 0.0
    moves: int = 0


@dataclass
class GameAnalysisResult:
    reports: List[MoveReport] = field(default_factory=list)
    evals: List[Optional[int]] = field(default_factory=list)
    mates: List[Optional[int]] = field(default_factory=list)
    white: ColorSummary = field(default_factory=ColorSummary)
    black: ColorSummary = field(default_factory=ColorSummary)
    depth: int = 0
    complete: bool = False


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def pv_to_san(board: chess.Board, pv_uci: Sequence[str], limit: int = 12) -> List[str]:
    """Convert a UCI principal variation into SAN, stopping at the first illegal move."""
    temp = board.copy(stack=False)
    result: List[str] = []
    for uci in pv_uci[:limit]:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in temp.legal_moves:
            promoted = chess.Move.from_uci(uci + "q")
            if promoted in temp.legal_moves:
                move = promoted
            else:
                break
        result.append(temp.san(move))
        temp.push(move)
    return result


def _score_to_cp(info: Optional[EngineInfo]) -> tuple[Optional[int], Optional[int]]:
    if info is None:
        return None, None
    return info.cp_value(), info.score_mate


# ----------------------------------------------------------------------
# Analyzer thread
# ----------------------------------------------------------------------
class GameAnalyzer(QThread):
    """Analyses every position of a game and classifies each move."""

    progress = Signal(int, int)
    partialResult = Signal(object)
    analysisFinished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        engine: StockfishEngine,
        boards: Sequence[chess.Board],
        depth: int = 14,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._boards = list(boards)
        self._depth = max(1, int(depth))
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    @property
    def cancelled(self) -> bool:
        return self._stop.is_set()

    def run(self) -> None:
        try:
            boards = self._boards
            total = len(boards)
            if total == 0:
                self.analysisFinished.emit(GameAnalysisResult())
                return

            start_fen = boards[0].fen()
            lines_per_position: List[List[EngineInfo]] = []

            for index, board in enumerate(boards):
                if self._stop.is_set():
                    break
                move_list = [m.uci() for m in board.move_stack]
                _, lines = self._engine.analyse(
                    fen=start_fen,
                    moves=move_list or None,
                    depth=self._depth,
                    multipv=1,
                    stop_event=self._stop,
                )
                lines_per_position.append(lines)
                self.progress.emit(index + 1, total)

            if self._stop.is_set() and len(lines_per_position) < total:
                boards = boards[: len(lines_per_position)]

            result = self._build_result(boards, lines_per_position)
            result.complete = not self._stop.is_set()
            self.analysisFinished.emit(result)

        except EngineError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Game analysis failed: {exc}")

    def _build_result(
        self,
        boards: Sequence[chess.Board],
        lines_per_position: Sequence[Sequence[EngineInfo]],
    ) -> GameAnalysisResult:
        result = GameAnalysisResult(depth=self._depth)
        move_count = min(len(boards) - 1, max(0, len(lines_per_position) - 1))

        for ply in range(move_count):
            board_before = boards[ply]
            board_after = boards[ply + 1]

            before_info = lines_per_position[ply][0] if lines_per_position[ply] else None
            after_info = lines_per_position[ply + 1][0] if lines_per_position[ply + 1] else None

            cp_before, mate_before = _score_to_cp(before_info)
            cp_after, mate_after = _score_to_cp(after_info)

            move = board_after.peek() if board_after.move_stack else None
            if move is None:
                move = board_before.move_stack[-1] if board_before.move_stack else None
            if move is None:
                continue

            san = board_before.san(move)
            mover_is_white = board_before.turn == chess.WHITE

            if mover_is_white:
                mover_before, mover_after = cp_before, cp_after
            else:
                mover_before = None if cp_before is None else -cp_before
                mover_after = None if cp_after is None else -cp_after

            loss = 0
            if mover_before is not None and mover_after is not None:
                loss = int(max(0, mover_before - mover_after))

            best_uci = before_info.pv[0] if (before_info and before_info.pv) else ""
            best_san = ""
            if best_uci:
                sans = pv_to_san(board_before, [best_uci], limit=1)
                best_san = sans[0] if sans else ""
            classification = classify_move(loss, played_uci=move.uci(), best_uci=best_uci)

            accuracy = 100.0
            if mover_before is not None and mover_after is not None:
                accuracy = move_accuracy(mover_before, mover_after)

            pv_uci = list(before_info.pv) if before_info else []
            report = MoveReport(
                ply=ply,
                move=move,
                san=san,
                color=chess.WHITE if mover_is_white else chess.BLACK,
                eval_before=cp_before,
                eval_after=cp_after,
                mate_before=mate_before,
                mate_after=mate_after,
                cp_loss=loss,
                classification=classification,
                accuracy=accuracy,
                best_move_uci=best_uci,
                best_move_san=best_san,
                pv_uci=pv_uci,
                pv_san=pv_to_san(board_before, pv_uci),
            )

            result.reports.append(report)
            result.evals.append(cp_after)
            result.mates.append(mate_after)
            self.partialResult.emit(report)

        self._summarise(result)
        return result

    @staticmethod
    def _summarise(result: GameAnalysisResult) -> None:
        white = ColorSummary()
        black = ColorSummary()

        for report in result.reports:
            target = white if report.color == chess.WHITE else black
            target.moves += 1
            key = report.classification.lower()
            if key == "best":
                target.best += 1
            elif key == "excellent":
                target.excellent += 1
            elif key == "good":
                target.good += 1
            elif key == "inaccuracy":
                target.inaccuracy += 1
            elif key == "mistake":
                target.mistake += 1
            else:
                target.blunder += 1

        for summary, color in ((white, chess.WHITE), (black, chess.BLACK)):
            values = [r.accuracy for r in result.reports if r.color == color]
            summary.accuracy = sum(values) / len(values) if values else 0.0

        result.white = white
        result.black = black


# ----------------------------------------------------------------------
def build_boards(game, max_plies: Optional[int] = None) -> List[chess.Board]:
    """Return the list of positions of a PGN game (start position first)."""
    boards: List[chess.Board] = []
    board = game.board()
    boards.append(board.copy(stack=True))

    for index, move in enumerate(game.mainline_moves()):
        if max_plies is not None and index >= max_plies:
            break
        if move not in board.legal_moves:
            break
        board.push(move)
        boards.append(board.copy(stack=True))

    return boards
