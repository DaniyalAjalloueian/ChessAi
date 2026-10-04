"""Procedurally generated sound effects.

No external audio files are bundled.  On first run each effect is
synthesised as a short 16-bit mono WAV and cached in the user's config
folder.  Playback uses Qt's QSoundEffect, which never blocks the GUI.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path
from typing import Callable, Dict, List, Optional

import chess
from PySide6.QtCore import QObject, QUrl

try:
    from PySide6.QtMultimedia import QSoundEffect

    _HAS_MULTIMEDIA = True
except ImportError:  # pragma: no cover - PySide6 always ships this on Windows
    QSoundEffect = None  # type: ignore[assignment]
    _HAS_MULTIMEDIA = False


SAMPLE_RATE = 44100


# ----------------------------------------------------------------------
# Synthesis helpers
# ----------------------------------------------------------------------
def _envelope(t: float, duration: float, attack: float = 0.005) -> float:
    if t < attack:
        return t / attack
    u = (t - attack) / max(1e-6, duration - attack)
    return math.exp(-4.0 * u)


def _tone(
    freq: float,
    duration: float,
    amplitude: float = 0.6,
    kind: str = "sine",
) -> List[int]:
    n = int(SAMPLE_RATE * duration)
    samples: List[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _envelope(t, duration)
        if kind == "noise":
            value = random.uniform(-1.0, 1.0)
        elif kind == "mixed":
            value = 0.65 * math.sin(2 * math.pi * freq * t) + 0.35 * random.uniform(-1.0, 1.0)
        elif kind == "triangle":
            phase = (t * freq) % 1.0
            value = 4.0 * abs(phase - 0.5) - 1.0
        else:  # sine
            value = math.sin(2 * math.pi * freq * t)
        samples.append(int(max(-1.0, min(1.0, value * env * amplitude)) * 32767))
    return samples


def _sweep(
    start_freq: float,
    end_freq: float,
    duration: float,
    amplitude: float = 0.6,
) -> List[int]:
    n = int(SAMPLE_RATE * duration)
    samples: List[int] = []
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = start_freq + (end_freq - start_freq) * (t / duration)
        phase += 2 * math.pi * freq / SAMPLE_RATE
        env = _envelope(t, duration)
        value = math.sin(phase) * env * amplitude
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))
    return samples


def _silence(duration: float) -> List[int]:
    return [0] * int(SAMPLE_RATE * duration)


def _concat(*parts: List[int]) -> List[int]:
    out: List[int] = []
    for part in parts:
        out.extend(part)
    return out


def _write_wav(path: Path, samples: List[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(b"".join(struct.pack("<h", s) for s in samples))


# ----------------------------------------------------------------------
# Individual sound designs
# ----------------------------------------------------------------------
def _build_move() -> List[int]:
    return _tone(520, 0.075, amplitude=0.55)


def _build_capture() -> List[int]:
    return _concat(
        _tone(340, 0.09, amplitude=0.75, kind="mixed"),
        _tone(180, 0.06, amplitude=0.45),
    )


def _build_castle() -> List[int]:
    return _concat(
        _tone(500, 0.05, amplitude=0.55),
        _silence(0.03),
        _tone(500, 0.05, amplitude=0.55),
    )


def _build_check() -> List[int]:
    return _concat(
        _tone(880, 0.09, amplitude=0.6),
        _silence(0.02),
        _tone(1160, 0.10, amplitude=0.6),
    )


def _build_promote() -> List[int]:
    return _sweep(400, 950, 0.28, amplitude=0.6)


def _build_win() -> List[int]:
    return _concat(
        _tone(660, 0.12, amplitude=0.6),
        _silence(0.03),
        _tone(880, 0.12, amplitude=0.6),
        _silence(0.03),
        _tone(1320, 0.20, amplitude=0.6),
    )


def _build_lose() -> List[int]:
    return _concat(
        _tone(660, 0.14, amplitude=0.55),
        _silence(0.03),
        _tone(500, 0.14, amplitude=0.55),
        _silence(0.03),
        _tone(330, 0.24, amplitude=0.55),
    )


def _build_draw() -> List[int]:
    return _concat(
        _tone(500, 0.14, amplitude=0.5),
        _silence(0.05),
        _tone(500, 0.14, amplitude=0.5),
    )


_SOUND_BUILDERS: Dict[str, Callable[[], List[int]]] = {
    "move": _build_move,
    "capture": _build_capture,
    "castle": _build_castle,
    "check": _build_check,
    "promote": _build_promote,
    "win": _build_win,
    "lose": _build_lose,
    "draw": _build_draw,
}


# ----------------------------------------------------------------------
# Classification helper
# ----------------------------------------------------------------------
def classify_move_sound(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    perspective: Optional[bool] = None,
) -> str:
    """Return the sound name that best matches this move.

    `perspective` (chess.WHITE / chess.BLACK) is used for game-ending
    moves to decide between "win", "lose" and "draw".  When it is omitted
    the winning side is always announced with the "win" sound.
    """
    if board_after.is_checkmate():
        white_won = board_after.turn == chess.BLACK
        winner = chess.WHITE if white_won else chess.BLACK
        if perspective is None:
            return "win"
        return "win" if winner == perspective else "lose"

    if board_after.is_stalemate() or board_after.is_insufficient_material():
        return "draw"

    if board_after.is_check():
        return "check"

    if move.promotion:
        return "promote"

    if board_before.is_capture(move):
        return "capture"

    if board_before.is_castling(move):
        return "castle"

    return "move"


# ----------------------------------------------------------------------
# Sound manager
# ----------------------------------------------------------------------
class SoundManager(QObject):
    """Owns the cached sound effects and plays them on demand."""

    def __init__(
        self,
        cache_dir: Path,
        enabled: bool = True,
        volume: float = 0.6,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._cache_dir = Path(cache_dir)
        self._enabled = bool(enabled)
        self._volume = max(0.0, min(1.0, float(volume)))
        self._effects: Dict[str, "QSoundEffect"] = {}

        self._prepare_effects()

    # ------------------------------------------------------------------
    def _prepare_effects(self) -> None:
        if not _HAS_MULTIMEDIA or QSoundEffect is None:
            return
        for name, builder in _SOUND_BUILDERS.items():
            path = self._cache_dir / f"{name}.wav"
            if not path.is_file():
                try:
                    _write_wav(path, builder())
                except OSError:
                    continue
            try:
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(self._volume)
                self._effects[name] = effect
            except Exception:
                # Never let audio problems crash the application.
                continue

    # ------------------------------------------------------------------
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, float(volume)))
        for effect in self._effects.values():
            effect.setVolume(self._volume)

    def volume(self) -> float:
        return self._volume

    # ------------------------------------------------------------------
    def play(self, name: str) -> None:
        if not self._enabled:
            return
        effect = self._effects.get(name)
        if effect is None:
            return
        try:
            if effect.isPlaying():
                effect.stop()
            effect.play()
        except Exception:
            pass

    def play_for_move(
        self,
        board_before: chess.Board,
        move: chess.Move,
        board_after: chess.Board,
        perspective: Optional[bool] = None,
    ) -> None:
        self.play(classify_move_sound(board_before, move, board_after, perspective))