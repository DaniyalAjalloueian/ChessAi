# Local Chess AI

**Powerful offline chess analysis powered by Stockfish.**

A modern, polished Windows desktop chess application built with Python, PySide6
and python-chess. Everything runs locally — no cloud service, no online API and
no internet connection is required while using the application.

---

## 1. Requirements

| Component | Version |
|-----------|---------|
| Operating system | Windows 10 or Windows 11 (64-bit) |
| Python | 3.11 or newer (64-bit) |
| Stockfish | Any recent official build (16 or newer recommended) |
| RAM | 1 GB minimum, 2 GB recommended |
| Disk | ~250 MB (plus Stockfish) |

---

## 2. Installing Python

1. Download Python 3.11+ from <https://www.python.org/downloads/windows/>
2. During setup, tick **Add python.exe to PATH**.
3. Verify the installation:

```powershell
py -3.11 --version
```

---

## 3. Installing the dependencies

From the project root:

```powershell
scripts\install.bat
```

Or manually:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 4. Installing Stockfish

This application does **not** bundle Stockfish. Download it yourself from:

<https://stockfishchess.org/download/>

Choose the **Windows x64** build that matches your CPU (AVX2 or BMI2 for modern
processors, plain `x86-64` for older ones). Extract the archive so you end up
with a file such as:

```text
stockfish\stockfish-windows-x86-64-avx2.exe
```

---

## 5. Configuring Stockfish

The application searches for Stockfish automatically, in this order:

1. The `STOCKFISH_PATH` environment variable.
2. The application directory (including `engine\bin\`, `engine\`, `bin\`).
3. The system `PATH`.
4. Common Windows install locations (`Program Files`, `Downloads`, …).
5. A path chosen manually on the **Settings** page.

The simplest approach is to copy the executable into:

```text
engine\bin\stockfish.exe
```

Alternatively set an environment variable (persistent):

```powershell
setx STOCKFISH_PATH "C:\Tools\Stockfish\stockfish.exe"
```

…or open **Settings → Stockfish → Browse** and pick `stockfish.exe`, then press
**Test Engine**.

---

## 6. Running the application

```powershell
scripts\run.bat
```

Or manually:

```powershell
.venv\Scripts\activate
python main.py
```

---

## 7. Building a standalone EXE

```powershell
scripts\build.bat
```

Or manually:

```powershell
.venv\Scripts\activate
pyinstaller --noconfirm --clean LocalChessAI.spec
```

Result:

```text
dist\
└── LocalChessAI\
    ├── LocalChessAI.exe
    ├── assets\
    └── ...
```

After packaging, place `stockfish.exe` inside `dist\LocalChessAI\engine\bin\`
(or select it from Settings). Python is not required to run the packaged build.

**License note:** do not redistribute the bundled Stockfish binary without
checking its GPLv3 requirements first.

---

## 8. Troubleshooting

| Problem | Solution |
|---------|----------|
| “Stockfish Engine Not Found” | Download Stockfish and select `stockfish.exe` in **Settings**, or place it in `engine\bin\`. |
| Engine starts but never returns a move | Press **Test Engine** in Settings. Make sure the file is a genuine Stockfish build and not blocked by antivirus. |
| The UI freezes | It shouldn't — all engine work runs on background threads. Press **Stop Analysis** to cancel a long search. |
| `ImportError: DLL load failed` for PySide6 | Install the Microsoft Visual C++ 2015-2022 Redistributable. |
| Invalid FEN message | FEN strings need at least the board layout and the side to move, e.g. `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1`. |
| PGN does not load | Ensure it contains at least one move. The app shows the parser warnings it encounters. |
| Antivirus blocks the built EXE | Add an exclusion or rebuild without UPX (`upx=False` in the spec file). |

---

## 9. Project architecture

```text
main.py                  Application entry point
app/                     Configuration, theme, utilities
engine/                  UCI wrapper, engine discovery, background tasks
core/                    Chess domain logic (game state, FEN, PGN, metrics)
ui/                      PySide6 widgets and pages
assets/                  Optional piece images and icons
scripts/                 Windows install / run / build helpers
```

Key classes:

| Class | Responsibility |
|-------|----------------|
| `Config` | JSON-backed persistent settings |
| `StockfishEngine` | Thread-safe UCI process wrapper |
| `EngineManager` | Discovery, engine ownership, task factory |
| `EngineTask` | One cancellable engine search on a `QThread` |
| `GameAnalyzer` | Full-game analysis, classification, accuracy |
| `GameController` | Board state with undo/redo |
| `ChessBoardWidget` | Custom-painted interactive board |
| `EvaluationBar` / `EvaluationGraph` | Evaluation visualisation |
| `MoveListWidget` | Clickable SAN move list |
| `MainWindow` | Page stack and navigation |

### Move classification

Moves are classified by **centipawn loss** relative to the engine's best line,
measured from the mover's point of view:

| Loss (cp) | Label |
|-----------|-------|
| best move, or ≤ 5 | Best |
| < 20 | Excellent |
| < 50 | Good |
| < 100 | Inaccuracy |
| < 250 | Mistake |
| ≥ 250 | Blunder |

Accuracy is estimated per move using the logistic win-probability curve and the
exponential accuracy mapping published by the Lichess project. **This is our own
engine-based approximation — it is not identical to any commercial website's
proprietary algorithm.**

---

## 10. License notes

* This application is released under the MIT License (see `LICENSE`).
* **Stockfish** is a separate program licensed under the **GNU GPL v3**. It is
  not included in this repository. If you redistribute it together with this
  application you must comply with the GPL.
* **python-chess** is licensed under the GNU GPL v3.
* **PySide6** is available under the LGPL v3 / commercial Qt license.
* **pyqtgraph** is licensed under the MIT License.