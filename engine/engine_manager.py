"""Stockfish discovery, engine ownership and background analysis tasks."""
from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from PySide6.QtCore import QObject, QThread, Signal

from app.utils import app_dir, resource_path
from engine.stockfish import EngineError, EngineInfo, StockfishEngine


# ----------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------
def _engine_name_patterns() -> List[str]:
    return ["stockfish*.exe", "Stockfish*.exe"]


def find_stockfish() -> Optional[str]:
    """Search the machine for a Stockfish executable.

    Order: STOCKFISH_PATH -> application directory -> PATH ->
    common Windows installation folders.
    """
    # 1. Environment variable
    env_value = os.environ.get("STOCKFISH_PATH", "").strip()
    if env_value:
        candidate = Path(env_value)
        if candidate.is_file():
            return str(candidate)
        if candidate.is_dir():
            for pattern in _engine_name_patterns():
                for found in sorted(candidate.glob(pattern)):
                    return str(found)

    # 2. Application directory and typical bundled folders
    bases = [app_dir(), resource_path("")]
    subdirs = ["", "engine/bin", "engine", "bin", "stockfish", "engine/stockfish", "assets/engine"]
    for base in bases:
        for sub in subdirs:
            directory = Path(base) / sub if sub else Path(base)
            if not directory.is_dir():
                continue
            for pattern in _engine_name_patterns():
                for found in sorted(directory.glob(pattern)):
                    return str(found)

    # 3. System PATH
    which = shutil.which("stockfish")
    if which:
        return which

    # 4. Common Windows install locations
    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("USERPROFILE"),
    ]
    subpaths = [
        "Stockfish",
        r"Programs\Stockfish",
        r"Downloads\Stockfish",
        r"Downloads\stockfish",
        r"Desktop\Stockfish",
    ]
    for root in roots:
        if not root:
            continue
        for sub in subpaths:
            directory = Path(root) / sub
            if not directory.is_dir():
                continue
            for pattern in _engine_name_patterns():
                for found in sorted(directory.glob(pattern)):
                    return str(found)
                for found in sorted(directory.glob(f"*/{pattern[0]}")):
                    return str(found)

    return None


def test_engine(path: str | Path) -> tuple[bool, str]:
    """Start the given executable and report (ok, engine name / error)."""
    engine = StockfishEngine(path, threads=1, hash_mb=16)
    try:
        engine.start()
        return True, engine.name
    except EngineError as exc:
        return False, str(exc)
    finally:
        engine.quit()


# ----------------------------------------------------------------------
# Background task
# ----------------------------------------------------------------------
@dataclass
class AnalysisOutcome:
    """Result of one engine search."""

    bestmove: Optional[str]
    lines: List[EngineInfo] = field(default_factory=list)
    cancelled: bool = False


class EngineTask(QThread):
    """Runs a single Stockfish search on a worker thread."""

    infoReady = Signal(object)      # EngineInfo
    finishedOk = Signal(object)     # AnalysisOutcome
    failed = Signal(str)

    _MIN_EMIT_INTERVAL = 0.10

    def __init__(
        self,
        engine: StockfishEngine,
        fen: str,
        moves: Optional[Sequence[str]] = None,
        depth: Optional[int] = None,
        movetime: Optional[float] = None,
        multipv: int = 1,
        skill: Optional[int] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._fen = fen
        self._moves = list(moves) if moves else None
        self._depth = depth
        self._movetime = movetime
        self._multipv = multipv
        self._skill = skill
        self._stop = threading.Event()
        self._last_emit = 0.0
        self.outcome: Optional[AnalysisOutcome] = None

    # ------------------------------------------------------------------
    def cancel(self) -> None:
        self._stop.set()

    @property
    def cancelled(self) -> bool:
        return self._stop.is_set()

    # ------------------------------------------------------------------
    def _on_info(self, info: EngineInfo) -> None:
        now = time.monotonic()
        if now - self._last_emit < self._MIN_EMIT_INTERVAL:
            return
        self._last_emit = now
        self.infoReady.emit(info)

    def run(self) -> None:  # noqa: D102 - QThread entry point
        try:
            bestmove, lines = self._engine.analyse(
                fen=self._fen,
                moves=self._moves,
                depth=self._depth,
                movetime=self._movetime,
                multipv=self._multipv,
                skill=self._skill,
                on_info=self._on_info,
                stop_event=self._stop,
            )
            outcome = AnalysisOutcome(bestmove, lines, self._stop.is_set())
            self.outcome = outcome
            self.finishedOk.emit(outcome)
        except EngineError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(f"Unexpected engine error: {exc}")


# ----------------------------------------------------------------------
# Manager
# ----------------------------------------------------------------------
class EngineManager(QObject):
    """Owns the Stockfish process and hands out analysis tasks."""

    optionsChanged = Signal()

    def __init__(self, config, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._engine: Optional[StockfishEngine] = None
        self._tasks: List[EngineTask] = []

    # ------------------------------------------------------------------
    def resolve_path(self) -> Optional[str]:
        stored = str(self._config.get("stockfish_path") or "").strip()
        if stored and Path(stored).is_file():
            return stored
        found = find_stockfish()
        if found:
            self._config.set("stockfish_path", found)
        return found

    def engine_path(self) -> Optional[str]:
        return self.resolve_path()

    def is_available(self) -> bool:
        return self.resolve_path() is not None

    def ensure_engine(self) -> StockfishEngine:
        path = self.resolve_path()
        if not path:
            raise EngineError(
                "Stockfish engine not found.\n\n"
                "Please install Stockfish and select stockfish.exe from Settings."
            )

        threads = int(self._config.get("threads", 2) or 2)
        hash_mb = int(self._config.get("hash_mb", 128) or 128)

        if self._engine is not None and self._engine.path != path:
            self._engine.quit()
            self._engine = None

        if self._engine is None:
            self._engine = StockfishEngine(path, threads=threads, hash_mb=hash_mb)
        else:
            self._engine.apply_options(threads=threads, hash_mb=hash_mb)

        return self._engine

    def apply_options(self) -> None:
        """Push thread/hash settings to a running engine."""
        if self._engine is None:
            return
        threads = int(self._config.get("threads", 2) or 2)
        hash_mb = int(self._config.get("hash_mb", 128) or 128)
        self._engine.apply_options(threads=threads, hash_mb=hash_mb)
        self.optionsChanged.emit()

    # ------------------------------------------------------------------
    def create_task(
        self,
        fen: str,
        moves: Optional[Sequence[str]] = None,
        depth: Optional[int] = None,
        movetime: Optional[float] = None,
        multipv: int = 1,
        skill: Optional[int] = None,
    ) -> EngineTask:
        engine = self.ensure_engine()
        task = EngineTask(
            engine,
            fen=fen,
            moves=moves,
            depth=depth,
            movetime=movetime,
            multipv=multipv,
            skill=skill,
            parent=self,
        )
        self._tasks.append(task)
        task.finished.connect(lambda: self._forget(task))
        return task

    def _forget(self, task: EngineTask) -> None:
        if task in self._tasks:
            self._tasks.remove(task)

    def running_tasks(self) -> List[EngineTask]:
        return list(self._tasks)

    def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    def wait_for_tasks(self, timeout_ms: int = 5000) -> None:
        for task in list(self._tasks):
            task.cancel()
        for task in list(self._tasks):
            if task.isRunning():
                task.wait(timeout_ms)

    def shutdown(self) -> None:
        self.wait_for_tasks(4000)
        if self._engine is not None:
            self._engine.quit()
            self._engine = None