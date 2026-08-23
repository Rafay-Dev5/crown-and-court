"""Compare balance sign-off at standard vs PRD-recommended sample sizes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from analytics.auto_tune import run_balance_pipeline
from analytics.export_viewer_balance import export_viewer_balance
from analytics.sweeps import run_sweep


def _load_gate_targets() -> dict[str, float]:
    path = Path("configs/balance_targets.yaml")
    if not path.exists():
        return {"assisted_max": 0.12, "shield_min": 0.25, "shield_max": 0.70, "spread_max": 0.20}
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pc = data.get("phase_c_requires") or data
    return {
        "assisted_max": float(pc.get("assisted_win_rate_max", data.get("assisted_win_rate_max", 0.12))),
        "shield_min": float(pc.get("shield_hit_rate_min", data.get("shield_hit_rate_min", 0.25))),
        "shield_max": float(pc.get("shield_hit_rate_max", data.get("shield_hit_rate_max", 0.70))),
        "spread_max": float(pc.get("seat_win_rate_spread_max", data.get("seat_win_rate_spread_max", 0.20))),
    }


def _score(metrics: dict[str, Any], min_games: int, games_run: int) -> dict[str, Any]:
    gates = _load_gate_targets()
    assisted = float(metrics.get("assisted_win_rate", 1))
    shield = float(metrics.get("shield_hit_rate", 0))
    role = metrics.get("role_win_rate", {})
    king_wr = float(role.get("started_as_king", 0))
    role_min = 0.35
    role_max = 0.45
    role_ok = role_min <= king_wr <= role_max
    seat_rates = [float(v) for v in metrics.get("win_rates_by_seat", {}).values()]
    spread = max(seat_rates) - min(seat_rates) if seat_rates else 0

    sample_ok = games_run >= min_games
    assisted_ok = assisted <= gates["assisted_max"]
    shield_ok = gates["shield_min"] <= shield <= gates["shield_max"]
    spread_ok = spread <= gates["spread_max"]

    points = sum([sample_ok, assisted_ok, shield_ok, spread_ok, role_ok])
    return {
        "assisted_win_rate": assisted,
        "shield_hit_rate": shield,
        "started_as_king_win_rate": king_wr,
        "seat_win_spread": spread,
        "role_win_rate_in_band": role_ok,
        "shield_in_prd_band": shield_ok,
        "assisted_under_cap": assisted_ok,
        "sample_sufficient": sample_ok,
        "gates_passed": points,
        "gates_total": 5,
        "signoff_ready": points >= 5 and sample_ok,
        "phase_c_ready": points >= 5 and sample_ok,
    }


def compare_signoff(
    games_standard: int = 100,
    games_prd: int = 385,
    seed: int = 0,
    tune_standard: bool = True,
) -> dict[str, Any]:
    min_n = 385

    if tune_standard:
        tuned = run_balance_pipeline(
            games=games_standard,
            kingmaker_games=200,
            seed=seed,
            tune=True,
            dry_run=False,
        )
        standard_metrics = tuned["final_sweep"]["metrics"]
        standard_games = tuned["final_sweep"]["games_run"]
    else:
        standard = run_sweep("configs/balance.yaml", games=games_standard, seed=seed)
        standard_metrics = standard["metrics"]
        standard_games = standard["games_run"]

    prd = run_sweep("configs/balance.yaml", games=games_prd, seed=seed + 50000)
    prd_metrics = prd["metrics"]

    standard_score = _score(standard_metrics, min_n, standard_games)
    prd_score = _score(prd_metrics, min_n, prd["games_run"])

    if prd_score["gates_passed"] > standard_score["gates_passed"]:
        recommendation = "prd_385"
        reason = "PRD sample (385 games) passes more balance gates with tighter CI."
    elif prd_score["gates_passed"] == standard_score["gates_passed"] and prd_score["sample_sufficient"]:
        recommendation = "prd_385"
        reason = "Both pass equally; prefer 385 games for statistical sign-off per PRD."
    elif standard_score["signoff_ready"]:
        recommendation = "standard_tuned"
        reason = "Tuned 100-game pass is acceptable for iteration; run 385 before print."
    else:
        recommendation = "prd_385"
        reason = "Standard pass did not meet gates; use 385-game metrics for decisions."

    result = {
        "standard_tuned_run": {
            "games": standard_games,
            "card_set_version": prd.get("card_set_version"),
            "score": standard_score,
            "metrics": {
                "assisted_win_rate": standard_metrics.get("assisted_win_rate"),
                "shield_hit_rate": standard_metrics.get("shield_hit_rate"),
                "role_win_rate": standard_metrics.get("role_win_rate"),
            },
        },
        "prd_sample_run": {
            "games": prd["games_run"],
            "card_set_version": prd["card_set_version"],
            "score": prd_score,
            "metrics": {
                "assisted_win_rate": prd_metrics.get("assisted_win_rate"),
                "assisted_win_modes": prd_metrics.get("assisted_win_modes"),
                "shield_hit_rate": prd_metrics.get("shield_hit_rate"),
                "shield_block_rate": prd_metrics.get("shield_block_rate"),
                "role_win_rate": prd_metrics.get("role_win_rate"),
            },
            "diagnostics": prd_metrics.get("diagnostics"),
        },
        "recommendation": recommendation,
        "reason": reason,
    }

    out = Path("game_logs/signoff_comparison.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    Path("game_logs/sweep_result.json").write_text(json.dumps(prd, indent=2), encoding="utf-8")
    if prd.get("metrics", {}).get("diagnostics"):
        Path("game_logs/diagnostics.json").write_text(
            json.dumps(prd["metrics"]["diagnostics"], indent=2), encoding="utf-8"
        )
    export_viewer_balance("game_logs/sweep_result.json")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare balance at 100 vs 385 games")
    parser.add_argument("--games-standard", type=int, default=100)
    parser.add_argument("--games-prd", type=int, default=385)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-tune", action="store_true")
    args = parser.parse_args()
    result = compare_signoff(
        args.games_standard,
        args.games_prd,
        args.seed,
        tune_standard=not args.no_tune,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
