"""Application settings: engine, performance, sound and appearance."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.sounds import SoundManager
from app.theme import BOARD_THEMES
from engine.engine_manager import EngineManager, find_stockfish, test_engine
from ui import dialogs

HASH_SIZES = [16, 32, 64, 128, 256, 512, 1024]

PIECE_SETS = ["Glyphs"]


class SettingsPage(QWidget):
    """Lets the user configure Stockfish, sound and the board appearance."""

    requestNavigate = Signal(str)
    settingsChanged = Signal()

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

        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(18)

        heading = QLabel("Settings")
        heading.setObjectName("H1")
        root.addWidget(heading)

        subtitle = QLabel(
            "Configure the Stockfish engine, performance, sound and appearance."
        )
        subtitle.setObjectName("Subtitle")
        root.addWidget(subtitle)

        root.addWidget(self._build_engine_group())
        root.addWidget(self._build_performance_group())
        root.addWidget(self._build_sound_group())
        root.addWidget(self._build_appearance_group())
        root.addStretch(1)

        footer = QHBoxLayout()
        save_button = QPushButton("Save Settings")
        save_button.setObjectName("Primary")
        save_button.setMinimumHeight(40)
        save_button.clicked.connect(self.save)
        footer.addWidget(save_button)

        back_button = QPushButton("Back to Menu")
        back_button.setObjectName("Ghost")
        back_button.setMinimumHeight(40)
        back_button.clicked.connect(lambda: self.requestNavigate.emit("home"))
        footer.addWidget(back_button)

        footer.addStretch(1)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    def _build_engine_group(self) -> QGroupBox:
        group = QGroupBox("Stockfish")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"C:\ChessAI\stockfish\stockfish.exe")
        row.addWidget(self.path_edit, 1)

        browse = QPushButton("Browse")
        browse.setMinimumHeight(32)
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        detect = QPushButton("Auto-Detect")
        detect.setMinimumHeight(32)
        detect.clicked.connect(self._auto_detect)
        buttons.addWidget(detect)

        test = QPushButton("Test Engine")
        test.setMinimumHeight(32)
        test.clicked.connect(self._test_engine)
        buttons.addWidget(test)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.engine_status = QLabel("No engine selected.")
        self.engine_status.setObjectName("Muted")
        self.engine_status.setWordWrap(True)
        layout.addWidget(self.engine_status)

        hint = QLabel(
            "The STOCKFISH_PATH environment variable is also checked automatically. "
            "Stockfish is a separate program and is not bundled with this application."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return group

    # ------------------------------------------------------------------
    def _build_performance_group(self) -> QGroupBox:
        group = QGroupBox("Performance")
        form = QFormLayout(group)
        form.setSpacing(10)

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, max(1, os.cpu_count() or 1))
        form.addRow("Engine Threads", self.threads_spin)

        self.hash_combo = QComboBox()
        for size in HASH_SIZES:
            self.hash_combo.addItem(f"{size} MB", size)
        form.addRow("Hash", self.hash_combo)

        return group

    # ------------------------------------------------------------------
    def _build_sound_group(self) -> QGroupBox:
        group = QGroupBox("Sound")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.sound_enabled_check = QCheckBox("Enable sound effects")
        self.sound_enabled_check.stateChanged.connect(self._on_sound_preview)
        layout.addWidget(self.sound_enabled_check)

        volume_row = QHBoxLayout()
        volume_row.setSpacing(10)
        volume_row.addWidget(QLabel("Volume"))

        self.sound_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.sound_volume_slider.setRange(0, 100)
        self.sound_volume_slider.setValue(60)
        self.sound_volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_row.addWidget(self.sound_volume_slider, 1)

        self.sound_volume_label = QLabel("60%")
        self.sound_volume_label.setMinimumWidth(42)
        self.sound_volume_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        volume_row.addWidget(self.sound_volume_label)
        layout.addLayout(volume_row)

        test_row = QHBoxLayout()
        test_button = QPushButton("Preview Move")
        test_button.setMinimumHeight(32)
        test_button.clicked.connect(lambda: self._sounds.play("move"))
        test_row.addWidget(test_button)

        capture_button = QPushButton("Preview Capture")
        capture_button.setMinimumHeight(32)
        capture_button.clicked.connect(lambda: self._sounds.play("capture"))
        test_row.addWidget(capture_button)

        test_row.addStretch(1)
        layout.addLayout(test_row)

        return group

    # ------------------------------------------------------------------
    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("Appearance")
        form = QFormLayout(group)
        form.setSpacing(10)

        self.board_combo = QComboBox()
        self.board_combo.addItems(list(BOARD_THEMES.keys()))
        form.addRow("Board Theme", self.board_combo)

        self.piece_combo = QComboBox()
        self.piece_combo.addItems(PIECE_SETS)
        form.addRow("Piece Set", self.piece_combo)

        note = QLabel(
            "Additional piece sets can be added as PNG or SVG files inside "
            "assets/pieces/<set name>/ (for example wK.png, bQ.svg)."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        form.addRow(note)

        return group

    # ------------------------------------------------------------------
    def _load_values(self) -> None:
        self.path_edit.setText(str(self._config.get("stockfish_path") or ""))
        self.threads_spin.setValue(int(self._config.get("threads", 2) or 2))

        hash_value = int(self._config.get("hash_mb", 128) or 128)
        index = self.hash_combo.findData(hash_value)
        self.hash_combo.setCurrentIndex(index if index >= 0 else 3)

        sound_enabled = bool(self._config.get("sound_enabled", True))
        self.sound_enabled_check.blockSignals(True)
        self.sound_enabled_check.setChecked(sound_enabled)
        self.sound_enabled_check.blockSignals(False)

        volume = float(self._config.get("sound_volume", 0.6) or 0.6)
        volume_percent = int(round(max(0.0, min(1.0, volume)) * 100))
        self.sound_volume_slider.blockSignals(True)
        self.sound_volume_slider.setValue(volume_percent)
        self.sound_volume_slider.blockSignals(False)
        self.sound_volume_label.setText(f"{volume_percent}%")
        self.sound_volume_slider.setEnabled(sound_enabled)

        theme = str(self._config.get("board_theme", "Green"))
        if theme in BOARD_THEMES:
            self.board_combo.setCurrentText(theme)

        piece_set = str(self._config.get("piece_set", "Glyphs"))
        if piece_set in PIECE_SETS:
            self.piece_combo.setCurrentText(piece_set)

        self._update_status()

    def _update_status(self) -> None:
        path = self.path_edit.text().strip()
        if path and Path(path).is_file():
            self.engine_status.setText(f"Engine file found:\n{path}")
        else:
            found = find_stockfish()
            if found:
                self.engine_status.setText(f"Detected engine:\n{found}")
            else:
                self.engine_status.setText(
                    "Stockfish was not detected automatically. "
                    "Use Browse to select stockfish.exe."
                )

    # ------------------------------------------------------------------
    def _on_sound_preview(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self.sound_volume_slider.setEnabled(enabled)
        self._sounds.set_enabled(enabled)
        if enabled:
            self._sounds.play("move")

    def _on_volume_changed(self, value: int) -> None:
        self.sound_volume_label.setText(f"{value}%")
        self._sounds.set_volume(value / 100.0)

    # ------------------------------------------------------------------
    def _browse(self) -> None:
        start = self.path_edit.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Stockfish Executable", start, "Executables (*.exe);;All Files (*)"
        )
        if path:
            self.path_edit.setText(path)
            self._update_status()

    def _auto_detect(self) -> None:
        found = find_stockfish()
        if not found:
            dialogs.warn(
                self,
                "Stockfish Engine Not Found",
                "Stockfish could not be located automatically.\n\n"
                "Download it from https://stockfishchess.org/download/ and select "
                "stockfish.exe manually, or set the STOCKFISH_PATH environment variable.",
            )
            return
        self.path_edit.setText(found)
        self._update_status()

    def _test_engine(self) -> None:
        path = self.path_edit.text().strip()
        if not path:
            dialogs.warn(self, "Test Engine", "Please select a Stockfish executable first.")
            return
        ok, message = test_engine(path)
        if ok:
            dialogs.info(self, "Test Engine", f"Engine responded successfully.\n\nIdentified as: {message}")
        else:
            dialogs.error(self, "Test Engine", f"The engine could not be started.\n\n{message}")

    # ------------------------------------------------------------------
    def save(self) -> None:
        path = self.path_edit.text().strip()
        if path and not Path(path).is_file():
            dialogs.error(
                self,
                "Invalid Engine Path",
                "The selected file does not exist.\nPlease choose a valid stockfish.exe.",
            )
            return

        previous_path = self._config.get("stockfish_path")
        sound_enabled = self.sound_enabled_check.isChecked()
        sound_volume = self.sound_volume_slider.value() / 100.0

        self._config.update(
            {
                "stockfish_path": path,
                "threads": self.threads_spin.value(),
                "hash_mb": self.hash_combo.currentData(),
                "board_theme": self.board_combo.currentText(),
                "piece_set": self.piece_combo.currentText(),
                "sound_enabled": sound_enabled,
                "sound_volume": sound_volume,
            }
        )
        self._config.save()

        if previous_path != path:
            self._engine_manager.shutdown()

        self._engine_manager.apply_options()

        self._sounds.set_enabled(sound_enabled)
        self._sounds.set_volume(sound_volume)

        self.settingsChanged.emit()
        dialogs.info(self, "Settings", "Settings saved successfully.")

    # ------------------------------------------------------------------
    def refresh_settings(self) -> None:
        self._load_values()