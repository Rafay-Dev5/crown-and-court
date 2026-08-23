from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LiveMetricsWriter:
    """Writes training progress to JSON for the viewer dashboard."""

    output_dir: Path
    viewer_public_dir: Path | None = None
    history_limit: int = 200

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.viewer_public_dir:
            self.viewer_public_dir.mkdir(parents=True, exist_ok=True)
        self._history: list[dict[str, Any]] = []
        self._started = time.time()

    @property
    def live_path(self) -> Path:
        return self.output_dir / "live.json"

    def write(
        self,
        *,
        status: str,
        episode: int,
        total_episodes: int,
        metrics: dict[str, Any],
        message: str = "",
        benchmark_history: list[dict[str, Any]] | None = None,
        series: dict[str, list[list[float]]] | None = None,
    ) -> None:
        payload = {
            "status": status,
            "started_at": self._started,
            "updated_at": time.time(),
            "episode": episode,
            "total_episodes": total_episodes,
            "progress_pct": round(100 * episode / max(1, total_episodes), 1),
            "message": message,
            "metrics": metrics,
            "benchmark_history": benchmark_history or [],
            "series": series or {},
            "history": self._history[-self.history_limit :],
        }
        text = json.dumps(payload, indent=2)
        self.live_path.write_text(text, encoding="utf-8")
        if self.viewer_public_dir:
            (self.viewer_public_dir / "live.json").write_text(text, encoding="utf-8")

    def record_episode(self, record: dict[str, Any]) -> None:
        self._history.append(record)

    def preload_history(self, records: list[dict[str, Any]]) -> None:
        """Restore episode table after resume (does not append to jsonl)."""
        self._history = list(records[-self.history_limit :])

    def append_history_file(self, record: dict[str, Any]) -> None:
        hist_path = self.output_dir / "history.jsonl"
        with hist_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
