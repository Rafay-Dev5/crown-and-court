"""Diagnose assisted-win and shield failure modes from game event logs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def analyze_assisted_wins(log: list[dict[str, Any]]) -> dict[str, Any]:
    winner_seat = winner_person = starting_king_person = None
    gifts: list[dict[str, Any]] = []
    for event in log:
        if event["type"] == "game_setup":
            skp = event.get("starting_king_person")
            if skp is not None:
                starting_king_person = int(skp)
        if event["type"] == "game_end":
            winner_seat = event.get("winner_seat")
            winner_person = event.get("winner_person")
        if event["type"] == "gold_gifted":
            gifts.append(event)

    if winner_seat is None:
        return {"assisted": False}

    gifts_to_winner = [g for g in gifts if g.get("to_seat") == winner_seat]
    gifts_to_winner_person = [
        g for g in gifts if winner_person is not None and g.get("to_person") == winner_person
    ]
    assisted = bool(gifts_to_winner_person) if winner_person is not None else bool(gifts_to_winner)
    total_gifted = sum(int(g.get("amount", 0)) for g in gifts_to_winner_person or gifts_to_winner)
    gift_count = len(gifts_to_winner_person or gifts_to_winner)

    modes: list[str] = []
    if assisted:
        if winner_person is not None and starting_king_person is not None:
            if int(winner_person) == int(starting_king_person):
                modes.append("starting_king_received_gifts")
            else:
                modes.append("ascended_noble_received_gifts")
        if len(gifts_to_winner_person or gifts_to_winner) >= 3:
            modes.append("multi_trade_stacking")
        if total_gifted >= 300:
            modes.append("high_volume_gifts")
        if not modes:
            modes.append("single_or_few_gifts")

    return {
        "assisted": assisted,
        "gift_count_to_winner": gift_count,
        "total_gifted_to_winner": total_gifted,
        "modes": modes,
    }


def analyze_shield_events(log: list[dict[str, Any]]) -> dict[str, Any]:
    hits = whiffs = blocks = 0
    whiff_reasons: Counter = Counter()
    trigger_types: Counter = Counter()
    by_card: dict[str, dict[str, int]] = defaultdict(lambda: {"hit": 0, "whiff": 0, "block": 0})

    for event in log:
        et = event["type"]
        cid = str(event.get("card_id", ""))
        if et == "protection_hit":
            hits += 1
            by_card[cid]["hit"] += 1
            trigger_types[str(event.get("trigger_type", "unknown"))] += 1
        elif et == "protection_whiff":
            whiffs += 1
            by_card[cid]["whiff"] += 1
            whiff_reasons[event.get("whiff_reason", "unknown")] += 1
            trigger_types[str(event.get("trigger_type", "unknown"))] += 1
        elif et == "shield_blocked":
            blocks += 1
            by_card[cid]["block"] += 1

    total = hits + whiffs
    return {
        "protection_trigger_hit_rate": hits / total if total else 0.0,
        "shield_block_count": blocks,
        "whiff_reasons": dict(whiff_reasons),
        "trigger_types": dict(trigger_types),
        "by_card": dict(by_card),
    }


def run_diagnostics(logs: list[list[dict[str, Any]]]) -> dict[str, Any]:
    assisted_games = 0
    mode_counts: Counter = Counter()
    hits = whiffs = blocks = 0
    whiff_reasons: Counter = Counter()
    trigger_types: Counter = Counter()
    shield_by_card: dict[str, dict[str, int]] = defaultdict(lambda: {"hit": 0, "whiff": 0, "block": 0})

    for log in logs:
        aw = analyze_assisted_wins(log)
        if aw.get("assisted"):
            assisted_games += 1
            for m in aw.get("modes", []):
                mode_counts[m] += 1
        sh = analyze_shield_events(log)
        for cid, counts in sh.get("by_card", {}).items():
            for k, v in counts.items():
                shield_by_card[cid][k] += v
        for event in log:
            if event["type"] == "protection_hit":
                hits += 1
                trigger_types[str(event.get("trigger_type", "unknown"))] += 1
            elif event["type"] == "protection_whiff":
                whiffs += 1
                whiff_reasons[event.get("whiff_reason", "unknown")] += 1
                trigger_types[str(event.get("trigger_type", "unknown"))] += 1
            elif event["type"] == "shield_blocked":
                blocks += 1

    total = len(logs)
    sh_total = hits + whiffs
    return {
        "games": total,
        "assisted_win_rate": assisted_games / total if total else 0.0,
        "assisted_win_modes": dict(mode_counts),
        "protection_hit_rate": hits / sh_total if sh_total else 0.0,
        "shield_block_count": blocks,
        "shield_block_rate": blocks / sh_total if sh_total else 0.0,
        "whiff_reasons": dict(whiff_reasons),
        "trigger_types": dict(trigger_types),
        "shield_by_card": dict(shield_by_card),
    }


def export_diagnostics(logs: list[list[dict[str, Any]]], out_path: str | Path) -> dict[str, Any]:
    result = run_diagnostics(logs)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run balance diagnostics on a sweep result")
    parser.add_argument("--sweep", default="game_logs/sweep_result.json")
    parser.add_argument("--out", default="game_logs/diagnostics.json")
    args = parser.parse_args()
    sweep_path = Path(args.sweep)
    if not sweep_path.exists():
        print(f"Missing {sweep_path} — run make sweep first")
        return
    sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
    diag = sweep.get("metrics", {}).get("diagnostics")
    if diag:
        Path(args.out).write_text(json.dumps(diag, indent=2), encoding="utf-8")
        print(json.dumps(diag, indent=2))
        return
    print("Sweep has no embedded diagnostics — re-run make sweep")


if __name__ == "__main__":
    main()
