"""Export balance sweep data for the card gallery viewer (plain + technical layers)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from analytics.metrics import METRIC_EXPLANATIONS, SEAT_LABELS
from engine.cards import load_all_cards


def _card_name_map() -> dict[str, str]:
    return {c["id"]: c.get("name", c["id"]) for c in load_all_cards()}


def _verdict(delta: float, games: int) -> str:
    if games < 5:
        return "too_few_games"
    if delta >= 0.12:
        return "overperformer"
    if delta <= -0.12:
        return "underperformer"
    return "balanced"


def _layman_verdict(verdict: str) -> str:
    return {
        "overperformer": "May be too strong — consider nerfing numbers or raising cost.",
        "underperformer": "Rarely helps the player who plays it win — consider buffing or redesign.",
        "balanced": "Within expected range for random playtesting.",
        "too_few_games": "Not enough data yet — play more simulated games.",
    }[verdict]


def _status_assisted(rate: float, max_target: float = 0.12) -> str:
    if rate <= max_target:
        return "good"
    if rate <= 0.25:
        return "watch"
    return "problem"


def export_viewer_balance(
    sweep_path: str | Path = "game_logs/sweep_result.json",
    kingmaker_path: str | Path = "game_logs/kingmaker_ab.json",
    tune_path: str | Path | None = "game_logs/tune_result.json",
    out_path: str | Path = "viewer/public/balance/summary.json",
) -> dict[str, Any]:
    sweep_file = Path(sweep_path)
    if not sweep_file.exists():
        payload = {
            "status": "idle",
            "message": "No balance sweep yet. Run: python -m analytics.auto_tune --games 80",
            "generated_at": None,
        }
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    sweep = json.loads(sweep_file.read_text(encoding="utf-8"))
    metrics = sweep.get("metrics", {})
    names = _card_name_map()
    total = int(metrics.get("total_games", 0))
    win_by_seat = metrics.get("win_rates_by_seat", {})
    fair = 1.0 / max(1, len(win_by_seat) or int(sweep.get("config", {}).get("num_players", 6)))

    seat_chart = []
    for seat_key in sorted(win_by_seat.keys(), key=lambda x: int(x)):
        seat = int(seat_key)
        rate = float(win_by_seat[seat_key])
        wins = int(round(rate * total))
        seat_chart.append(
            {
                "seat": seat,
                "label": SEAT_LABELS.get(seat, f"Seat {seat}"),
                "win_rate": rate,
                "wins": wins,
                "games": total,
                "delta_vs_fair": rate - fair,
                "layman": (
                    f"Sat here at the start and won {wins} of {total} games ({rate:.0%}). "
                    f"Fair share would be about {fair:.0%}."
                ),
            }
        )

    contributions = []
    raw = metrics.get("card_win_contribution", {})
    pick_counts = metrics.get("card_pick_counts", {})
    for cid, stats in raw.items():
        games = int(stats.get("games_with_card", 0))
        rate = float(stats.get("win_rate_when_played", 0))
        delta = float(stats.get("delta_vs_fair", 0))
        v = _verdict(delta, games)
        contributions.append(
            {
                "id": cid,
                "name": names.get(cid, cid),
                "times_played": int(pick_counts.get(cid, 0)),
                "games_with_card": games,
                "wins_when_played": int(stats.get("wins_when_played", 0)),
                "win_rate_when_played": rate,
                "delta_vs_fair": delta,
                "verdict": v,
                "layman": (
                    f"When this card hit the table, the player who played it won "
                    f"{stats.get('wins_when_played', 0)} of {games} games ({rate:.0%}). "
                    f"{_layman_verdict(v)}"
                ),
            }
        )
    contributions.sort(key=lambda x: x["delta_vs_fair"], reverse=True)

    role_contributions = []
    raw_by_role = metrics.get("card_win_contribution_by_role", {})
    for cid, roles in raw_by_role.items():
        for role, stats in roles.items():
            games = int(stats.get("games_with_card", 0))
            rate = float(stats.get("win_rate_when_played", 0))
            delta = float(stats.get("delta_vs_fair", 0))
            v = _verdict(delta, games)
            role_contributions.append(
                {
                    "id": cid,
                    "name": names.get(cid, cid),
                    "played_as_role": role,
                    "games_with_card": games,
                    "wins_when_played": int(stats.get("wins_when_played", 0)),
                    "win_rate_when_played": rate,
                    "delta_vs_fair": delta,
                    "verdict": v,
                    "layman": (
                        f"Played as {role.title()} in {games} games — "
                        f"won {stats.get('wins_when_played', 0)} ({rate:.0%}). {_layman_verdict(v)}"
                    ),
                }
            )
    role_contributions.sort(key=lambda x: abs(x["delta_vs_fair"]), reverse=True)

    diagnostics = metrics.get("diagnostics", {})
    diag_path = Path("game_logs/diagnostics.json")
    if diag_path.exists() and not diagnostics:
        diagnostics = json.loads(diag_path.read_text(encoding="utf-8"))

    role = metrics.get("role_win_rate", {})
    assisted = float(metrics.get("assisted_win_rate", 0))
    shield_hit = float(metrics.get("shield_hit_rate", 0))

    kingmaker = None
    km_path = Path(kingmaker_path)
    if km_path.exists():
        km = json.loads(km_path.read_text(encoding="utf-8"))
        off = km.get("gold_only", {})
        on = km.get("earned_gold_ledger", {})
        kingmaker = {
            "fix_works": km.get("fix_reduces_assisted_wins", False),
            "gold_only_ascension": float(off.get("gift_recipient_ascension_rate", 0)),
            "earned_gold_ascension": float(on.get("gift_recipient_ascension_rate", 0)),
            "layman": (
                "We tested a rigged scenario: a losing player gifts gold to a friend. "
                f"Without the earned-gold rule, that friend becomes King {off.get('gift_recipient_ascension_rate', 0):.0%} of the time. "
                f"With the rule, it drops to {on.get('gift_recipient_ascension_rate', 0):.0%}."
            ),
        }

    tune_summary = None
    signoff = None
    signoff_path = Path("game_logs/signoff_comparison.json")
    if signoff_path.exists():
        signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
    if tune_path and Path(tune_path).exists():
        tune = json.loads(Path(tune_path).read_text(encoding="utf-8"))
        final_tune = tune.get("final_tune", {})
        tune_summary = {
            "passes": tune.get("passes", 0),
            "changes_count": len(final_tune.get("changes_applied", [])),
            "recommendations": final_tune.get("recommendations", []),
        }

    payload: dict[str, Any] = {
        "status": "ready",
        "generated_at": sweep_file.stat().st_mtime,
        "card_set_version": sweep.get("card_set_version"),
        "games_run": sweep.get("games_run", total),
        "min_recommended_games": sweep.get("min_recommended_n"),
        "methodology": {
            "bots": sweep.get("bot_mode", "league_heuristic"),
            "seat_bots": sweep.get("seat_bots", []),
            "bots_layman": "Each seat runs a different play style (cautious, aggressive, alliance-focused, etc.) with smart dice/card choices — not random.",
            "purpose": "Simulate intentional play styles to stress-test cards and kingmaking rules.",
            "developer_note": "Sweep uses agents.heuristic seat_bots + smart_choice_policy. Training rotates PPO updates across all seats.",
        },
        "training_choices_note": {
            "layman": "Balance sweeps use smart heuristic choices for every seat. During training, each seat gets its own learned policy that picks cards and dice branches; opponents still use heuristics with smart choices.",
            "trained_seat": "Rotates across all seats when train_all_seats is true. Policy picks play indices and choice branches.",
            "opponent_bots": "League heuristics with smart_choice_policy (not random).",
        },
        "headlines": {
            "assisted_win_rate": assisted,
            "assisted_status": _status_assisted(assisted),
            "assisted_layman": (
                f"In {assisted:.0%} of games, the winner had received gifted gold during the game. "
                "Lower is better — high values suggest kingmaking or runaway gifts."
            ),
            "shield_hit_rate": shield_hit,
            "shield_block_rate": float(metrics.get("shield_block_rate", 0)),
            "shield_layman": (
                f"Protection guesses resolved correctly {shield_hit:.0%} of the time; "
                f"shields blocked attacks {float(metrics.get('shield_block_rate', 0)):.0%} of plays."
            ),
            "started_as_king_win_rate": float(role.get("started_as_king", 0)),
            "started_as_noble_win_rate": float(role.get("started_as_noble", 0)),
            "role_layman": (
                f"The player who started as King won {role.get('started_as_king', 0):.0%} of games; "
                f"Nobles who started behind won {role.get('started_as_noble', 0):.0%}."
            ),
        },
        "seat_chart": seat_chart,
        "card_contributions": contributions,
        "card_contributions_by_role": role_contributions[:30],
        "diagnostics": diagnostics,
        "kingmaker": kingmaker,
        "signoff_comparison": signoff,
        "tune": tune_summary,
        "metric_explanations": METRIC_EXPLANATIONS,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Export balance JSON for card gallery viewer")
    parser.add_argument("--sweep", default="game_logs/sweep_result.json")
    parser.add_argument("--kingmaker", default="game_logs/kingmaker_ab.json")
    parser.add_argument("--tune", default="game_logs/tune_result.json")
    parser.add_argument("--out", default="viewer/public/balance/summary.json")
    args = parser.parse_args()
    result = export_viewer_balance(args.sweep, args.kingmaker, args.tune, args.out)
    print(f"Exported balance viewer data: status={result.get('status')}")


if __name__ == "__main__":
    main()
