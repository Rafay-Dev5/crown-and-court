from __future__ import annotations

import argparse
import json
from pathlib import Path


def format_replay(events: list[dict]) -> str:
    lines = ["# Game Replay", ""]
    for event in events:
        rnd = event.get("round", "?")
        phase = event.get("phase", "?")
        etype = event.get("type", "?")
        extra = {k: v for k, v in event.items() if k not in ("type", "round", "phase")}
        detail = ", ".join(f"{k}={v}" for k, v in extra.items())
        lines.append(f"**R{rnd}** [{phase}] `{etype}` — {detail}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert JSONL game log to readable replay")
    parser.add_argument("logfile")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    events = []
    with Path(args.logfile).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    replay = format_replay(events)
    if args.out:
        Path(args.out).write_text(replay, encoding="utf-8")
        print(f"Replay written to {args.out}")
    else:
        print(replay)


if __name__ == "__main__":
    main()
