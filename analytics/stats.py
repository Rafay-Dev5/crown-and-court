"""Statistical helpers for balance analytics."""

from __future__ import annotations

import math


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion."""
    if trials == 0:
        return (0.0, 1.0)
    p = successes / trials
    denom = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))
    return (max(0.0, center - margin), min(1.0, center + margin))


def min_sample_size(
    baseline: float = 0.5,
    margin: float = 0.05,
    confidence: float = 0.95,
) -> int:
    """Minimum N for proportion estimate within margin at given confidence."""
    z_map = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_map.get(confidence, 1.96)
    if margin <= 0:
        return 100
    n = (z**2 * baseline * (1 - baseline)) / (margin**2)
    return max(30, math.ceil(n))


def exploitability_estimate(policy_win_rate: float, best_response_win_rate: float) -> float:
    """Gap between current policy and estimated best-response — higher = more exploitable."""
    return max(0.0, best_response_win_rate - policy_win_rate)
