from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from analytics.sweeps import run_sweep


def ablation(card_id: str, games: int = 50, seed: int = 0) -> dict:
    root = Path(__file__).resolve().parent.parent
    king = root / "cards" / "king_deck"
    noble = root / "cards" / "noble_deck"
    backup = root / "game_logs" / "ablation_backup"
    backup.mkdir(parents=True, exist_ok=True)

    moved: list[tuple[Path, Path]] = []
    for deck in (king, noble):
        for path in list(deck.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("id") == card_id:
                dest = backup / f"{deck.name}_{path.name}"
                shutil.move(str(path), str(dest))
                moved.append((path, dest))

    baseline = run_sweep("configs/balance.yaml", games, seed)
    for orig, dest in moved:
        shutil.move(str(dest), str(orig))

    without = run_sweep("configs/balance.yaml", games, seed + 5000)
    return {
        "card_id": card_id,
        "with_card": baseline["metrics"],
        "without_card": without["metrics"],
        "moved_files": [str(p) for p in moved],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Card ablation comparison")
    parser.add_argument("--card", required=True)
    parser.add_argument("--games", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    result = ablation(args.card, args.games, args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
