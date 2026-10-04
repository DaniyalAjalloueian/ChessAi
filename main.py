"""Local Chess AI - application entry point."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable when launched as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import Config
from app.theme import build_stylesheet
from app.utils import resource_path
from ui.main_window import MainWindow


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Local Chess AI")
    app.setOrganizationName("LocalChessAI")
    app.setApplicationDisplayName("Local Chess AI")
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    icon_path = resource_path("assets/icons/app.png")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    config = Config()
    window = MainWindow(config)
    window.show()

    exit_code = app.exec()
    window.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())