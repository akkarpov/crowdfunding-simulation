"""Сопоставимые стресс-прогоны альтернатив для матрицы решений."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.capacity import run_series

OPTIONS = {
    "base": {}, "r2_3": {"R2": 3}, "r3_3": {"R3": 3}, "r4_5": {"R4": 5},
    "redistribute": {"R2": 1, "R3": 3}, "redistribute_r4_5": {"R2": 1, "R3": 3, "R4": 5},
}

if __name__ == "__main__":
    run_series("stress.jsonl", [(name, seed, 6, caps, 504, True, {})
                               for name, caps in OPTIONS.items() for seed in range(7801, 7807)])
