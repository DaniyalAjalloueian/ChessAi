"""Engine-based move classification and accuracy metrics.

The thresholds implemented here are *our own* documented approximation.
They are inspired by publicly available engine-analysis conventions but
are NOT identical to any commercial chess website's proprietary formula.
"""
from __future__ import annotations

import math
from typing import Optional

# Mate scores are mapped to a large centipawn value.
MATE_CP = 10_000

# Centipawn-loss thresholds (from the mover's point of view).
THRESHOLD_EXCELLENT = 20
THRESHOLD_GOOD = 50
THRESHOLD_INACCURACY = 100
THRESHOLD_MISTAKE = 250

CLASSIFICATIONS = [
    "Best",
    "Excellent",
    "Good",
    "Inaccuracy",
    "Mistake",
    "Blunder",
]


def classify_move(cp_loss: int, played_uci: str = "", best_uci: str = "") -> str:
    """Return a classification label for a move."""
    if best_uci and played_uci and played_uci == best_uci:
        return "Best"

    loss = max(0, int(cp_loss))
    if loss <= 5:
        return "Best"
    if loss < THRESHOLD_EXCELLENT:
        return "Excellent"
    if loss < THRESHOLD_GOOD:
        return "Good"
    if loss < THRESHOLD_INACCURACY:
        return "Inaccuracy"
    if loss < THRESHOLD_MISTAKE:
        return "Mistake"
    return "Blunder"


def win_percentage(cp: int) -> float:
    """Convert a centipawn score into an expected-score percentage.

    Uses the logistic curve published by the Lichess project.
    """
    if cp >= MATE_CP - 100:
        return 100.0
    if cp <= -(MATE_CP - 100):
        return 0.0
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0)


def move_accuracy(cp_before: int, cp_after: int) -> float:
    """Per-move accuracy in percent (Lichess-style approximation)."""
    before = win_percentage(cp_before)
    after = win_percentage(cp_after)
    drop = max(0.0, before - after)
    value = 103.1668 * math.exp(-0.04354 * drop) - 3.1669
    return max(0.0, min(100.0, value))


def accuracy_from_losses(losses) -> float:
    """Average accuracy for a sequence of already-computed per-move accuracies."""
    values = [v for v in losses if v is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def eval_to_plot(cp: Optional[int], mate: Optional[int], cap: float = 8.0) -> float:
    """Convert an evaluation into a plottable value in pawns, clamped for display."""
    if mate is not None:
        if mate == 0:
            return 0.0
        return cap if mate > 0 else -cap
    if cp is None:
        return 0.0
    value = cp / 100.0
    return max(-cap, min(cap, value))


def advantage_fraction(cp: Optional[int], mate: Optional[int]) -> float:
    """Return White's share of the evaluation bar, from 0.0 to 1.0."""
    if mate is not None:
        if mate == 0:
            return 0.5
        return 1.0 if mate > 0 else 0.0
    if cp is None:
        return 0.5
    return win_percentage(cp) / 100.0