"""Poll GPU training until episode 5000, then run post-training benchmark."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "game_logs" / "training" / "live.json"
CHECKPOINTS = ROOT / "game_logs" / "training" / "checkpoints"
OUT = ROOT / "game_logs" / "training" / "benchmark_post_5k.json"
POLL_SEC = 60
TARGET_EPISODES = 5000


def _latest_checkpoint() -> Path | None:
    files = sorted(CHECKPOINTS.glob("policy_ep*.json"))
    return files[-1] if files else None


def _training_complete() -> bool:
    if not LIVE.exists():
        return False
    data = json.loads(LIVE.read_text(encoding="utf-8"))
    return data.get("status") == "complete" and int(data.get("episode", 0)) >= TARGET_EPISODES


def main() -> None:
    print(f"Waiting for episode {TARGET_EPISODES} (poll every {POLL_SEC}s)...")
    while not _training_complete():
        if LIVE.exists():
            data = json.loads(LIVE.read_text(encoding="utf-8"))
            print(
                f"  {data.get('status')}: ep {data.get('episode')}/{data.get('total_episodes')} "
                f"({data.get('progress_pct')}%) backend={data.get('metrics', {}).get('policy_backend')}"
            )
        time.sleep(POLL_SEC)

    ckpt = _latest_checkpoint()
    if not ckpt:
        sys.exit("No checkpoint found")
    print(f"Benchmarking {ckpt.name}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "training.benchmark",
            "--config",
            "configs/training.yaml",
            "--games",
            "100",
            "--seed",
            "42",
            "--checkpoint",
            str(ckpt),
            "--out",
            str(OUT),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "training.benchmark",
            "--config",
            "configs/training.yaml",
            "--games",
            "100",
            "--seed",
            "42",
            "--checkpoint",
            str(ckpt),
            "--out",
            str(ROOT / "game_logs" / "training" / "benchmark.json"),
        ],
        cwd=ROOT,
        check=True,
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
