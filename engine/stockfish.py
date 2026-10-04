"""Low level, thread-safe UCI wrapper around the Stockfish engine."""
from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence


class EngineError(RuntimeError):
    """Raised when the engine cannot be started, or stops responding."""


@dataclass
class EngineInfo:
    """A single parsed `info` line, normalised to White's point of view."""

    depth: int = 0
    seldepth: int = 0
    multipv: int = 1
    score_cp: Optional[int] = None
    score_mate: Optional[int] = None
    nodes: int = 0
    nps: int = 0
    time_ms: int = 0
    pv: List[str] = field(default_factory=list)
    lowerbound: bool = False
    upperbound: bool = False

    @property
    def has_score(self) -> bool:
        return self.score_cp is not None or self.score_mate is not None

    def eval_text(self) -> str:
        if self.score_mate is not None:
            if self.score_mate == 0:
                return "#"
            return f"M{abs(self.score_mate)}" if self.score_mate > 0 else f"-M{abs(self.score_mate)}"
        if self.score_cp is None:
            return "0.00"
        return f"{self.score_cp / 100.0:+.2f}"

    def cp_value(self) -> Optional[int]:
        """Return the score as centipawns (mate mapped to a large value)."""
        if self.score_mate is not None:
            sign = 1 if self.score_mate > 0 else -1
            return sign * (10000 - min(abs(self.score_mate), 100) * 10)
        return self.score_cp


_INFO_INT_FIELDS = {
    "depth": "depth",
    "seldepth": "seldepth",
    "multipv": "multipv",
    "nodes": "nodes",
    "nps": "nps",
    "time": "time_ms",
    "hashfull": None,
    "tbhits": None,
    "cpuload": None,
    "currmovenumber": None,
}


class StockfishEngine:
    """Owns one Stockfish process and speaks UCI to it."""

    def __init__(self, path: str | Path, threads: int = 2, hash_mb: int = 128) -> None:
        self.path = str(path)
        self.threads = int(threads)
        self.hash_mb = int(hash_mb)
        self.name = "Stockfish"

        self._proc: Optional[subprocess.Popen] = None
        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._reader: Optional[threading.Thread] = None
        self._write_lock = threading.Lock()
        self._session_lock = threading.RLock()

    # ------------------------------------------------------------------
    # process lifecycle
    # ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        with self._session_lock:
            if self.is_running:
                return

            exe = Path(self.path)
            if not exe.is_file():
                raise EngineError(f"Stockfish executable was not found:\n{self.path}")

            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            try:
                self._proc = subprocess.Popen(
                    [str(exe)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(exe.parent),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creationflags,
                )
            except OSError as exc:
                raise EngineError(f"Could not start Stockfish:\n{exc}") from exc

            self._queue = queue.Queue()
            self._reader = threading.Thread(
                target=self._read_loop, name="stockfish-reader", daemon=True
            )
            self._reader.start()

            self._send("uci")
            lines = self._wait_for("uciok", timeout=20.0)
            for line in lines:
                if line.startswith("id name"):
                    self.name = line[len("id name"):].strip() or "Stockfish"

            self._send(f"setoption name Threads value {self.threads}")
            self._send(f"setoption name Hash value {self.hash_mb}")
            self._send("isready")
            self._wait_for("readyok", timeout=20.0)

    def quit(self) -> None:
        """Shut the engine process down gracefully."""
        with self._session_lock:
            proc = self._proc
            if proc is None:
                return
            self._proc = None
            try:
                if proc.poll() is None:
                    try:
                        if proc.stdin:
                            proc.stdin.write("quit\n")
                            proc.stdin.flush()
                    except (OSError, ValueError):
                        pass
                    try:
                        proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        try:
                            proc.wait(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            pass
            except OSError:
                pass

    # ------------------------------------------------------------------
    # low level IO
    # ------------------------------------------------------------------
    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            self._queue.put(None)
            return
        try:
            for raw in proc.stdout:
                self._queue.put(raw.rstrip("\r\n"))
        except (OSError, ValueError):
            pass
        finally:
            self._queue.put(None)

    def _send(self, command: str) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            raise EngineError("The Stockfish process is not running.")
        with self._write_lock:
            try:
                proc.stdin.write(command + "\n")
                proc.stdin.flush()
            except (OSError, ValueError) as exc:
                raise EngineError("Lost the connection to Stockfish.") from exc

    def _wait_for(self, token: str, timeout: float = 10.0) -> List[str]:
        collected: List[str] = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise EngineError(
                    f"Stockfish did not answer with '{token}' within {timeout:.0f} seconds."
                )
            try:
                line = self._queue.get(timeout=min(remaining, 0.25))
            except queue.Empty:
                continue
            if line is None:
                raise EngineError("The Stockfish process terminated unexpectedly.")
            collected.append(line)
            if line.startswith(token):
                return collected

    def _drain(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    # ------------------------------------------------------------------
    # options
    # ------------------------------------------------------------------
    def set_option(self, name: str, value: object) -> None:
        if not self.is_running:
            return
        try:
            self._send(f"setoption name {name} value {value}")
        except EngineError:
            pass

    def apply_options(self, threads: int | None = None, hash_mb: int | None = None) -> None:
        if threads is not None:
            self.threads = int(threads)
            self.set_option("Threads", self.threads)
        if hash_mb is not None:
            self.hash_mb = int(hash_mb)
            self.set_option("Hash", self.hash_mb)

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------
    def analyse(
        self,
        fen: str,
        moves: Optional[Sequence[str]] = None,
        depth: Optional[int] = None,
        movetime: Optional[float] = None,
        multipv: int = 1,
        skill: Optional[int] = None,
        on_info: Optional[Callable[[EngineInfo], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> tuple[Optional[str], List[EngineInfo]]:
        """Run one search and return (bestmove_uci, best lines).

        `movetime` is expressed in seconds.  When both `depth` and `movetime`
        are given Stockfish stops at whichever limit is reached first.
        """
        with self._session_lock:
            if not self.is_running:
                self.start()

            self._drain()
            self.set_option("MultiPV", max(1, int(multipv)))
            if skill is not None:
                self.set_option("Skill Level", max(0, min(20, int(skill))))

            position = f"position fen {fen}"
            if moves:
                position += " moves " + " ".join(moves)
            self._send(position)

            go_parts = ["go"]
            if depth:
                go_parts += ["depth", str(int(depth))]
            if movetime:
                go_parts += ["movetime", str(int(float(movetime) * 1000))]
            if len(go_parts) == 1:
                go_parts.append("infinite")
            self._send(" ".join(go_parts))

            white_to_move = fen.split()[1] == "w"
            if moves and len(moves) % 2 == 1:
                white_to_move = not white_to_move

            latest: Dict[int, EngineInfo] = {}
            bestmove: Optional[str] = None
            stopping = False

            while bestmove is None:
                if stop_event is not None and stop_event.is_set() and not stopping:
                    stopping = True
                    try:
                        self._send("stop")
                    except EngineError:
                        raise

                try:
                    line = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if line is None:
                    raise EngineError("The Stockfish process terminated unexpectedly.")

                if line.startswith("bestmove"):
                    parts = line.split()
                    bestmove = parts[1] if len(parts) > 1 else None
                    if bestmove in ("(none)", "0000"):
                        bestmove = None
                    break

                if line.startswith("info "):
                    info = self._parse_info(line, white_to_move)
                    if info is None or not info.has_score:
                        continue
                    if info.lowerbound or info.upperbound:
                        continue
                    if info.pv:
                        latest[info.multipv] = info
                        if on_info is not None:
                            try:
                                on_info(info)
                            except Exception:
                                pass

            ordered = [latest[key] for key in sorted(latest)]
            return bestmove, ordered

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_info(line: str, white_to_move: bool) -> Optional[EngineInfo]:
        tokens = line.split()
        if len(tokens) < 4:
            return None

        info = EngineInfo()
        index = 1
        count = len(tokens)

        while index < count:
            token = tokens[index]
            try:
                if token in _INFO_INT_FIELDS:
                    attribute = _INFO_INT_FIELDS[token]
                    if attribute and index + 1 < count:
                        setattr(info, attribute, int(tokens[index + 1]))
                    index += 2
                elif token == "score":
                    if index + 2 >= count:
                        break
                    kind = tokens[index + 1]
                    value = int(tokens[index + 2])
                    if not white_to_move:
                        value = -value
                    if kind == "cp":
                        info.score_cp = value
                    elif kind == "mate":
                        info.score_mate = value
                    index += 3
                    if index < count and tokens[index] in ("lowerbound", "upperbound"):
                        info.lowerbound = tokens[index] == "lowerbound"
                        info.upperbound = tokens[index] == "upperbound"
                        index += 1
                elif token == "pv":
                    info.pv = tokens[index + 1:]
                    break
                elif token in ("currmove", "wdl"):
                    index += 2
                elif token == "string":
                    break
                else:
                    index += 1
            except (ValueError, IndexError):
                return None

        return info

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            self.quit()
        except Exception:
            pass