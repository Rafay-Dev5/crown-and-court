from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class GameRNG:
    """Single seedable RNG for shuffles and dice rolls."""

    seed: int | None = None
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def shuffle(self, items: list) -> None:
        self._rng.shuffle(items)

    def randint(self, low: int, high: int) -> int:
        return self._rng.randint(low, high)

    def choice(self, seq: list):
        return self._rng.choice(seq)

    def random(self) -> float:
        return self._rng.random()

    def fork(self, offset: int = 0) -> GameRNG:
        """Derive a child RNG for sub-systems while keeping parent reproducible."""
        child = GameRNG(seed=None)
        child._rng.setstate(self._rng.getstate())
        for _ in range(offset):
            child._rng.random()
        return child
