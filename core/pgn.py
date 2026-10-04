"""PGN import / export helpers."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import chess
import chess.pgn


class PgnError(ValueError):
    """Raised when a PGN cannot be parsed."""


def read_pgn(text: str) -> Tuple[chess.pgn.Game, List[str]]:
    """Parse PGN text and return (game, warnings)."""
    if not text or not text.strip():
        raise PgnError("The PGN text is empty.")

    stream = io.StringIO(text)
    try:
        game = chess.pgn.read_game(stream)
    except Exception as exc:  # python-chess can raise various errors
        raise PgnError(f"Could not parse the PGN:\n{exc}") from exc

    if game is None:
        raise PgnError("No chess game was found in the supplied PGN.")

    warnings: List[str] = []
    if game.errors:
        for error in game.errors:
            warnings.append(str(error))
        warnings.append("Some moves may have been skipped while loading.")

    if not any(True for _ in game.mainline_moves()):
        warnings.append("The PGN does not contain any moves.")

    return game, warnings


def build_game(
    moves: List[chess.Move],
    start_fen: Optional[str] = None,
    white: str = "Player",
    black: str = "Stockfish",
    event: str = "Local Chess AI Game",
) -> chess.pgn.Game:
    """Create a PGN game object from a list of moves."""
    game = chess.pgn.Game()
    game.headers["Event"] = event
    game.headers["Site"] = "Local Chess AI"
    game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = "1"
    game.headers["White"] = white
    game.headers["Black"] = black

    board = chess.Board(start_fen) if start_fen else chess.Board()
    if start_fen and start_fen != chess.STARTING_FEN:
        game.headers["SetUp"] = "1"
        game.headers["FEN"] = start_fen

    node: chess.pgn.GameNode = game
    for move in moves:
        if move not in board.legal_moves:
            break
        node = node.add_variation(move)
        board.push(move)

    game.headers["Result"] = board.result(claim_draw=False)
    return game


def export_pgn(game: chess.pgn.Game, path: str | Path) -> None:
    """Write a PGN game to disk using UTF-8."""
    target = Path(path)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(str(game))
        handle.write("\n")


def pgn_text(game: chess.pgn.Game) -> str:
    return str(game)