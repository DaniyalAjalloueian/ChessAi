"""FEN validation and helpers."""
from __future__ import annotations

from typing import Optional, Tuple

import chess


def validate_fen(fen: str) -> Tuple[bool, str]:
    """Return (is_valid, error_message)."""
    text = (fen or "").strip()
    if not text:
        return False, "The FEN string is empty."

    parts = text.split()
    if len(parts) < 2:
        return False, "A FEN must contain at least the board and the side to move."

    try:
        chess.Board(text)
    except ValueError as exc:
        return False, str(exc)

    return True, ""


def normalise_fen(fen: str) -> str:
    """Return a fully expanded FEN (6 fields) if possible."""
    try:
        return chess.Board(fen).fen()
    except ValueError:
        return fen.strip()


def set_side_to_move(fen: str, white_to_move: bool) -> str:
    """Return a FEN with the given side to move (clears en-passant if invalid)."""
    try:
        board = chess.Board(fen)
    except ValueError:
        return fen
    board.turn = chess.WHITE if white_to_move else chess.BLACK
    if board.ep_square is not None and not board.has_legal_en_passant():
        board.ep_square = None
    return board.fen()


def side_to_move(fen: str) -> Optional[bool]:
    """True = White to move, False = Black, None when the FEN is invalid."""
    try:
        return chess.Board(fen).turn == chess.WHITE
    except ValueError:
        return None