"""Application shell: header bar plus a stacked page container."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import sounds_dir
from app.sounds import SoundManager
from engine.engine_manager import EngineManager
from ui.analysis_page import AnalysisPage
from ui.best_move_page import BestMovePage
from ui.home_page import HomePage
from ui.play_page import PlayPage
from ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    """Top level window that owns every page."""

    PAGE_INDEX = {
        "home": 0,
        "play": 1,
        "bestmove": 2,
        "analysis": 3,
        "settings": 4,
    }

    def __init__(self, config, parent=None) -> None:
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("Local Chess AI")
        self.resize(
            int(config.get("window_width", 1440) or 1440),
            int(config.get("window_height", 900) or 900),
        )
        self.setMinimumSize(1180, 780)

        self.engine_manager = EngineManager(config, self)
        self.sounds = SoundManager(
            cache_dir=sounds_dir(),
            enabled=bool(config.get("sound_enabled", True)),
            volume=float(config.get("sound_volume", 0.6) or 0.6),
            parent=self,
        )

        self._build_ui()
        self._connect_pages()
        self._check_engine_on_startup()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- header ---------------------------------------------------
        header = QWidget()
        header.setFixedHeight(58)
        header.setStyleSheet(
            "background-color: #171D22; border-bottom: 1px solid #2E3942;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 8, 20, 8)
        header_layout.setSpacing(12)

        self.back_button = QPushButton("\u2190  Home")
        self.back_button.setObjectName("Ghost")
        self.back_button.setMinimumHeight(34)
        self.back_button.clicked.connect(lambda: self.navigate("home"))
        header_layout.addWidget(self.back_button)

        title = QLabel("Local Chess AI")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        header_layout.addWidget(title)

        subtitle = QLabel("Powerful offline chess analysis powered by Stockfish")
        subtitle.setObjectName("Muted")
        header_layout.addWidget(subtitle)

        header_layout.addStretch(1)

        self.engine_badge = QLabel("Engine: checking...")
        self.engine_badge.setObjectName("Muted")
        header_layout.addWidget(self.engine_badge)

        settings_button = QPushButton("Settings")
        settings_button.setObjectName("Ghost")
        settings_button.setMinimumHeight(34)
        settings_button.clicked.connect(lambda: self.navigate("settings"))
        header_layout.addWidget(settings_button)

        layout.addWidget(header)

        # ---- pages ----------------------------------------------------
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.home_page = HomePage()
        self.play_page = PlayPage(self.engine_manager, self._config, self.sounds)
        self.best_move_page = BestMovePage(self.engine_manager, self._config, self.sounds)
        self.analysis_page = AnalysisPage(self.engine_manager, self._config, self.sounds)
        self.settings_page = SettingsPage(self.engine_manager, self._config, self.sounds)

        for page in (
            self.home_page,
            self.play_page,
            self.best_move_page,
            self.analysis_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)

        QShortcut(QKeySequence("Ctrl+H"), self, activated=lambda: self.navigate("home"))

    # ------------------------------------------------------------------
    def _connect_pages(self) -> None:
        for page in (self.home_page, self.play_page, self.best_move_page, self.analysis_page):
            page.requestNavigate.connect(self.navigate)
        self.settings_page.requestNavigate.connect(self.navigate)
        self.settings_page.settingsChanged.connect(self._on_settings_changed)

        self.engine_manager.optionsChanged.connect(self._refresh_engine_badge)

    # ------------------------------------------------------------------
    def navigate(self, name: str) -> None:
        index = self.PAGE_INDEX.get(name)
        if index is None:
            return
        self.stack.setCurrentIndex(index)
        self.back_button.setVisible(name != "home")

        if name == "play":
            self.play_page.refresh_settings()
        elif name == "bestmove":
            self.best_move_page.refresh_settings()
        elif name == "analysis":
            self.analysis_page.refresh_settings()
        elif name == "settings":
            self.settings_page.refresh_settings()

    # ------------------------------------------------------------------
    def _on_settings_changed(self) -> None:
        self.play_page.refresh_settings()
        self.best_move_page.refresh_settings()
        self.analysis_page.refresh_settings()
        self._refresh_engine_badge()

    def _check_engine_on_startup(self) -> None:
        self._refresh_engine_badge()

    def _refresh_engine_badge(self) -> None:
        path = self.engine_manager.engine_path()
        if path:
            name = path.replace("/", "\\").rsplit("\\", 1)[-1]
            self.engine_badge.setText(f"Engine: {name}")
            self.engine_badge.setStyleSheet("color: #4CAF7D;")
        else:
            self.engine_badge.setText("Engine: not found")
            self.engine_badge.setStyleSheet("color: #D9534F;")

    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._config.update(
            {"window_width": self.width(), "window_height": self.height()}
        )
        self._config.save()
        self.shutdown()
        event.accept()

    def shutdown(self) -> None:
        for page in (self.play_page, self.best_move_page, self.analysis_page):
            try:
                page.shutdown()
            except Exception:
                pass
        self.engine_manager.shutdown()
        self._config.save()