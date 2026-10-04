"""Custom-painted chess board widget.

Supports:
* Normal play: legal-move validation, click-to-move, drag-and-drop.
* Edit mode: free placement of any piece on any square, plus eraser.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import chess
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.theme import BOARD_THEMES
from app.utils import resource_path

PIECE_GLYPHS: Dict[str, str] = {
    "P": "\u265F",
    "N": "\u265E",
    "B": "\u265D",
    "R": "\u265C",
    "Q": "\u265B",
    "K": "\u265A",
}

WHITE_PIECE_GLYPHS: Dict[str, str] = {
    "P": "\u2659",
    "N": "\u2658",
    "B": "\u2657",
    "R": "\u2656",
    "Q": "\u2655",
    "K": "\u2654",
}

BLACK_PIECE_GLYPHS: Dict[str, str] = {
    "P": "\u265F",
    "N": "\u265E",
    "B": "\u265D",
    "R": "\u265C",
    "Q": "\u265B",
    "K": "\u265A",
}

PIECE_FILE_NAMES: Dict[int, str] = {
    chess.PAWN: "P",
    chess.KNIGHT: "N",
    chess.BISHOP: "B",
    chess.ROOK: "R",
    chess.QUEEN: "Q",
    chess.KING: "K",
}

WHITE_FILL = QColor("#F8F8F8")
WHITE_EDGE = QColor("#2B2B2B")
BLACK_FILL = QColor("#262D34")
BLACK_EDGE = QColor("#0B0E11")

_DRAG_THRESHOLD_SQ = 16


class ChessBoardWidget(QWidget):
    """An 8x8 board with normal play and free-edit modes."""

    moveRequested = Signal(object)          # chess.Move
    squareClicked = Signal(int)             # chess.Square
    promotionRequested = Signal(int, int)   # from_square, to_square
    positionEdited = Signal()               # emitted whenever the board contents change in edit mode

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._board = chess.Board()
        self._orientation = chess.WHITE
        self._selected: Optional[int] = None
        self._legal_targets: set[int] = set()
        self._last_move: Optional[chess.Move] = None
        self._arrows: List[Tuple[int, int, str]] = []
        self._interactive = True
        self._theme_name = "Green"
        self._piece_set = "Glyphs"
        self._show_coordinates = True

        # Edit mode
        self._edit_mode = False
        self._palette_piece: Optional[Tuple[int, bool]] = None
        self._palette_eraser = False

        # Drag state
        self._drag_square: Optional[int] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._drag_pos: Optional[QPointF] = None
        self._drag_active = False

        self._promotion_callback: Optional[Callable[[int, int], Optional[int]]] = None
        self._pixmap_cache: Dict[Tuple[str, int, int, int], Optional[QPixmap]] = {}

    # ------------------------------------------------------------------
    # sizing
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(600, 600)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(320, 320)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def set_board(self, board: chess.Board) -> None:
        self._board = board
        self._selected = None
        self._legal_targets.clear()
        self._cancel_drag()
        self.update()

    def board(self) -> chess.Board:
        return self._board

    def set_interactive(self, interactive: bool) -> None:
        self._interactive = interactive
        if not interactive:
            self._selected = None
            self._legal_targets.clear()
            self._cancel_drag()
        self._update_cursor()
        self.update()

    def set_orientation(self, color: bool) -> None:
        self._orientation = chess.WHITE if color == chess.WHITE else chess.BLACK
        self.update()

    def orientation(self) -> bool:
        return self._orientation

    def flip(self) -> None:
        self._orientation = not self._orientation
        self.update()

    def set_last_move(self, move: Optional[chess.Move]) -> None:
        self._last_move = move
        self.update()

    def set_arrows(self, arrows: Sequence[Tuple[int, int, str]]) -> None:
        self._arrows = list(arrows)
        self.update()

    def clear_arrows(self) -> None:
        self._arrows = []
        self.update()

    def set_theme(self, name: str) -> None:
        if name in BOARD_THEMES:
            self._theme_name = name
            self.update()

    def set_piece_set(self, name: str) -> None:
        self._piece_set = name
        self._pixmap_cache.clear()
        self.update()

    def set_promotion_callback(self, callback: Callable[[int, int], Optional[int]]) -> None:
        self._promotion_callback = callback

    def clear_selection(self) -> None:
        self._selected = None
        self._legal_targets.clear()
        self.update()

    # ------------------------------------------------------------------
    # edit mode API
    # ------------------------------------------------------------------
    def is_edit_mode(self) -> bool:
        return self._edit_mode

    def set_edit_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._edit_mode == enabled:
            return
        self._edit_mode = enabled
        self._selected = None
        self._legal_targets.clear()
        self._cancel_drag()
        self._update_cursor()
        self.update()

    def set_palette_piece(self, piece_type: int, color: bool) -> None:
        self._palette_piece = (piece_type, color)
        self._palette_eraser = False

    def set_palette_eraser(self, enabled: bool) -> None:
        self._palette_eraser = bool(enabled)
        if enabled:
            self._palette_piece = None

    def clear_palette(self) -> None:
        self._palette_piece = None
        self._palette_eraser = False

    # ------------------------------------------------------------------
    # geometry
    # ------------------------------------------------------------------
    def _square_size(self) -> float:
        return min(self.width(), self.height()) / 8.0

    def _origin(self) -> QPointF:
        size = self._square_size() * 8.0
        return QPointF((self.width() - size) / 2.0, (self.height() - size) / 2.0)

    def _square_rect(self, square: int) -> QRectF:
        size = self._square_size()
        origin = self._origin()
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self._orientation == chess.WHITE:
            column, row = file, 7 - rank
        else:
            column, row = 7 - file, rank
        return QRectF(origin.x() + column * size, origin.y() + row * size, size, size)

    def _square_at(self, point: QPointF) -> Optional[int]:
        size = self._square_size()
        origin = self._origin()
        if size <= 0:
            return None
        column = int((point.x() - origin.x()) // size)
        row = int((point.y() - origin.y()) // size)
        if column < 0 or column > 7 or row < 0 or row > 7:
            return None
        if self._orientation == chess.WHITE:
            file, rank = column, 7 - row
        else:
            file, rank = 7 - column, row
        return chess.square(file, rank)

    # ------------------------------------------------------------------
    # painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        size = self._square_size()
        light_hex, dark_hex = BOARD_THEMES.get(self._theme_name, BOARD_THEMES["Green"])
        light = QColor(light_hex)
        dark = QColor(dark_hex)

        # Squares
        for square in chess.SQUARES:
            rect = self._square_rect(square)
            color = light if (chess.square_file(square) + chess.square_rank(square)) % 2 else dark
            painter.fillRect(rect, color)

        # Board frame
        board_rect = QRectF(
            self._origin().x(),
            self._origin().y(),
            size * 8,
            size * 8,
        )
        painter.setPen(QPen(QColor("#0C1116"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(board_rect)

        # Last move highlight (only in normal mode)
        if not self._edit_mode and self._last_move is not None:
            highlight = QColor(246, 246, 105, 110)
            for square in (self._last_move.from_square, self._last_move.to_square):
                painter.fillRect(self._square_rect(square), highlight)

        # Check highlight (guarded — the position may not be legal in edit mode)
        if not self._edit_mode:
            try:
                in_check = self._board.is_check()
            except Exception:
                in_check = False
            if in_check:
                king_square = self._board.king(self._board.turn)
                if king_square is not None:
                    rect = self._square_rect(king_square)
                    gradient = QRadialGradient(rect.center(), rect.width() * 0.62)
                    gradient.setColorAt(0.0, QColor(255, 70, 70, 210))
                    gradient.setColorAt(1.0, QColor(255, 70, 70, 0))
                    painter.setBrush(QBrush(gradient))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(rect)

        # Selected square (only in normal mode)
        if not self._edit_mode and self._selected is not None:
            painter.fillRect(self._square_rect(self._selected), QColor(246, 246, 105, 150))

        # Legal move indicators (only in normal mode)
        if not self._edit_mode:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(20, 26, 32, 90)))
            for target in self._legal_targets:
                rect = self._square_rect(target)
                if self._board.piece_at(target) is not None:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(20, 26, 32, 110), max(3.0, rect.width() * 0.09)))
                    painter.drawEllipse(rect.adjusted(4, 4, -4, -4))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(20, 26, 32, 90)))
                else:
                    radius = rect.width() * 0.16
                    painter.drawEllipse(rect.center(), radius, radius)

        # Pieces (skip the piece currently being dragged)
        for square in chess.SQUARES:
            if self._drag_active and square == self._drag_square:
                continue
            piece = self._board.piece_at(square)
            if piece is None:
                continue
            self._draw_piece(painter, self._square_rect(square), piece)

        # The dragged piece following the cursor
        if (
            self._drag_active
            and self._drag_square is not None
            and self._drag_pos is not None
        ):
            piece = self._board.piece_at(self._drag_square)
            if piece is not None:
                rect = QRectF(
                    self._drag_pos.x() - size / 2,
                    self._drag_pos.y() - size / 2,
                    size,
                    size,
                )
                self._draw_piece(painter, rect, piece)

        # Coordinates
        if self._show_coordinates:
            self._draw_coordinates(painter)

        # Arrows
        for from_square, to_square, color in self._arrows:
            self._draw_arrow(painter, from_square, to_square, QColor(color))

        painter.end()

    # ------------------------------------------------------------------
    def _draw_piece(self, painter: QPainter, rect: QRectF, piece: chess.Piece) -> None:
        pixmap = self._load_piece_pixmap(piece, int(rect.width()))
        if pixmap is not None:
            x = rect.center().x() - pixmap.width() / 2.0
            y = rect.center().y() - pixmap.height() / 2.0
            painter.drawPixmap(QPointF(x, y), pixmap)
            return

        letter = chess.PIECE_SYMBOLS[piece.piece_type].upper()
        glyph = PIECE_GLYPHS.get(letter, "?")
        font = QFont("Segoe UI Symbol")
        font.setPixelSize(max(10, int(rect.height() * 0.80)))
        font.setWeight(QFont.Weight.Normal)

        metrics = QFontMetricsF(font)
        bounds = metrics.boundingRect(glyph)
        baseline_x = rect.center().x() - (bounds.left() + bounds.right()) / 2.0
        baseline_y = rect.center().y() - (bounds.top() + bounds.bottom()) / 2.0

        path = QPainterPath()
        path.addText(baseline_x, baseline_y, font, glyph)

        if piece.color == chess.WHITE:
            painter.setBrush(QBrush(WHITE_FILL))
            painter.setPen(QPen(WHITE_EDGE, max(1.0, rect.height() * 0.022)))
        else:
            painter.setBrush(QBrush(BLACK_FILL))
            painter.setPen(QPen(BLACK_EDGE, max(1.0, rect.height() * 0.022)))
        painter.drawPath(path)

    # ------------------------------------------------------------------
    def _load_piece_pixmap(self, piece: chess.Piece, size: int) -> Optional[QPixmap]:
        if self._piece_set == "Glyphs" or not self._piece_set:
            return None

        key = (self._piece_set, piece.color, piece.piece_type, size)
        if key in self._pixmap_cache:
            return self._pixmap_cache[key]

        color_prefix = "w" if piece.color == chess.WHITE else "b"
        letter = PIECE_FILE_NAMES.get(piece.piece_type, "P")
        base = resource_path(f"assets/pieces/{self._piece_set}")
        result: Optional[QPixmap] = None
        for extension in (".png", ".svg"):
            candidate = base / f"{color_prefix}{letter}{extension}"
            if candidate.is_file():
                pixmap = QPixmap(str(candidate))
                if not pixmap.isNull():
                    result = pixmap.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                break

        self._pixmap_cache[key] = result
        return result

    # ------------------------------------------------------------------
    def _draw_coordinates(self, painter: QPainter) -> None:
        size = self._square_size()
        font = QFont("Segoe UI", max(7, int(size * 0.20)))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)

        files = "abcdefgh"
        for column in range(8):
            file_index = column if self._orientation == chess.WHITE else 7 - column
            square = chess.square(file_index, 0 if self._orientation == chess.WHITE else 7)
            rect = self._square_rect(square)
            dark_square = (chess.square_file(square) + chess.square_rank(square)) % 2 == 0
            painter.setPen(QColor("#EDEDED") if dark_square else QColor("#3E4A52"))
            painter.drawText(
                QRectF(rect.right() - size * 0.26, rect.bottom() - size * 0.30, size * 0.22, size * 0.24),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                files[file_index],
            )

        for row in range(8):
            rank_index = 7 - row if self._orientation == chess.WHITE else row
            square = chess.square(0 if self._orientation == chess.WHITE else 7, rank_index)
            rect = self._square_rect(square)
            dark_square = (chess.square_file(square) + chess.square_rank(square)) % 2 == 0
            painter.setPen(QColor("#EDEDED") if dark_square else QColor("#3E4A52"))
            painter.drawText(
                QRectF(rect.left() + size * 0.06, rect.top() + size * 0.04, size * 0.22, size * 0.24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                str(rank_index + 1),
            )

    # ------------------------------------------------------------------
    def _draw_arrow(self, painter: QPainter, from_square: int, to_square: int, color: QColor) -> None:
        if from_square == to_square:
            return
        start_center = self._square_rect(from_square).center()
        end_center = self._square_rect(to_square).center()
        vector = end_center - start_center
        length = math.hypot(vector.x(), vector.y())
        if length < 1.0:
            return

        unit = QPointF(vector.x() / length, vector.y() / length)
        perpendicular = QPointF(-unit.y(), unit.x())
        size = self._square_size()

        start = start_center + unit * (size * 0.26)
        end = end_center - unit * (size * 0.30)

        pen = QPen(color, max(3.0, size * 0.16))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(start, end)

        head_length = size * 0.30
        head_width = size * 0.30
        tip = end_center - unit * (size * 0.10)
        left = tip - unit * head_length + perpendicular * (head_width * 0.5)
        right = tip - unit * head_length - perpendicular * (head_width * 0.5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(QPolygonF([tip, left, right]))

    # ------------------------------------------------------------------
    # interaction helpers
    # ------------------------------------------------------------------
    def _update_cursor(self) -> None:
        if not self._interactive:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self._drag_active:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._edit_mode and self._palette_piece is not None:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self._edit_mode and self._palette_eraser:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _cancel_drag(self) -> None:
        self._drag_square = None
        self._drag_start_pos = None
        self._drag_pos = None
        self._drag_active = False
        self._update_cursor()

    # ------------------------------------------------------------------
    # events
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._interactive:
            return

        square = self._square_at(event.position())
        if square is None:
            return

        # Right-click removes in edit mode.
        if event.button() == Qt.MouseButton.RightButton:
            if self._edit_mode and self._board.piece_at(square) is not None:
                self._board.remove_piece_at(square)
                self.update()
                self.positionEdited.emit()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        self.squareClicked.emit(square)

        if self._edit_mode:
            self._edit_press(square, event.position())
            return

        # ---- normal play ---------------------------------------------
        if (
            self._selected is not None
            and square in self._legal_targets
            and square != self._selected
        ):
            self._try_move(self._selected, square)
            return

        piece = self._board.piece_at(square)
        if piece is not None and piece.color == self._board.turn:
            self._selected = square
            self._legal_targets = {
                move.to_square
                for move in self._board.legal_moves
                if move.from_square == square
            }
            self._drag_square = square
            self._drag_start_pos = event.position()
            self._drag_pos = event.position()
            self._drag_active = False
            self.update()
            return

        self._selected = None
        self._legal_targets.clear()
        self.update()

    # ------------------------------------------------------------------
    def _edit_press(self, square: int, position: QPointF) -> None:
        # Eraser
        if self._palette_eraser:
            if self._board.piece_at(square) is not None:
                self._board.remove_piece_at(square)
                self.update()
                self.positionEdited.emit()
            return

        # Place a piece from the palette
        if self._palette_piece is not None:
            piece_type, color = self._palette_piece
            self._board.set_piece_at(square, chess.Piece(piece_type, color))
            self.update()
            self.positionEdited.emit()
            return

        # Free move: drag an existing piece
        piece = self._board.piece_at(square)
        if piece is None:
            return
        self._drag_square = square
        self._drag_start_pos = position
        self._drag_pos = position
        self._drag_active = False
        self._update_cursor()

    # ------------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_square is None or self._drag_start_pos is None:
            return

        if not self._drag_active:
            delta = event.position() - self._drag_start_pos
            if delta.x() * delta.x() + delta.y() * delta.y() < _DRAG_THRESHOLD_SQ:
                return
            self._drag_active = True
            self._update_cursor()

        self._drag_pos = event.position()
        self.update()

    # ------------------------------------------------------------------
    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_square is None:
            return

        origin = self._drag_square
        was_dragging = self._drag_active
        self._cancel_drag()

        if not was_dragging:
            self.update()
            return

        target = self._square_at(event.position())
        if target is None or target == origin:
            self.update()
            return

        # ---- edit mode: move freely, no legality check ---------------
        if self._edit_mode:
            piece = self._board.piece_at(origin)
            if piece is not None:
                self._board.remove_piece_at(origin)
                self._board.set_piece_at(target, piece)
                self.update()
                self.positionEdited.emit()
            return

        # ---- normal mode --------------------------------------------
        if target in self._legal_targets:
            self._try_move(origin, target)
            return

        self._selected = None
        self._legal_targets.clear()
        self.update()

    # ------------------------------------------------------------------
    def _try_move(self, from_square: int, to_square: int) -> None:
        promotion_moves = [
            move
            for move in self._board.legal_moves
            if move.from_square == from_square and move.to_square == to_square
        ]
        if not promotion_moves:
            self._selected = None
            self._legal_targets.clear()
            self.update()
            return

        if any(move.promotion for move in promotion_moves):
            promotion = None
            if self._promotion_callback is not None:
                promotion = self._promotion_callback(from_square, to_square)
            if promotion is None:
                self._selected = None
                self._legal_targets.clear()
                self.update()
                return
            move = chess.Move(from_square, to_square, promotion=promotion)
            if move not in self._board.legal_moves:
                move = next(m for m in promotion_moves if m.promotion == promotion)
        else:
            move = promotion_moves[0]

        self._selected = None
        self._legal_targets.clear()
        self.update()
        self.moveRequested.emit(move)