"""Interactive game state with undo / redo support."""
from __future__ import annotations

from typing import List, Optional

import chess


class GameController:
    """Thin wrapper around `chess.Board` that adds redo handling."""

    def __init__(self, fen: Optional[str] = None) -> None:
        self._start_fen = fen or chess.STARTING_FEN
        self.board = chess.Board(self._start_fen)
        self._redo: List[chess.Move] = []

    # ------------------------------------------------------------------
    @property
    def start_fen(self) -> str:
        return self._start_fen

    def reset(self, fen: Optional[str] = None) -> None:
        if fen:
            self._start_fen = fen
        self.board = chess.Board(self._start_fen)
        self._redo.clear()

    # ------------------------------------------------------------------
    def push(self, move: chess.Move) -> bool:
        if move not in self.board.legal_moves:
            return False
        self.board.push(move)
        self._redo.clear()
        return True

    def push_uci(self, uci: str) -> bool:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False
        if move not in self.board.legal_moves:
            promoted = chess.Move.from_uci(uci + "q")
            if promoted in self.board.legal_moves:
                move = promoted
            else:
                return False
        return self.push(move)

    def undo(self) -> Optional[chess.Move]:
        if not self.board.move_stack:
            return None
        move = self.board.pop()
        self._redo.append(move)
        return move

    def redo(self) -> Optional[chess.Move]:
        if not self._redo:
            return None
        move = self._redo.pop()
        self.board.push(move)
        return move

    # ------------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        return bool(self.board.move_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def move_history(self) -> List[chess.Move]:
        return list(self.board.move_stack)

    def fen(self) -> str:
        return self.board.fen()

    def is_game_over(self) -> bool:
        return self.board.is_game_over(claim_draw=False)

    def result_text(self) -> str:
        board = self.board
        if board.is_checkmate():
            return "1-0" if board.turn == chess.BLACK else "0-1"
        if (
            board.is_stalemate()
            or board.is_insufficient_material()
            or board.is_seventyfive_moves()
            or board.is_fivefold_repetition()
        ):
            return "1/2-1/2"
        return "*"