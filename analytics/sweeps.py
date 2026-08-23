from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from agents.heuristic.seat_policies import resolve_seat_bots
from analytics.diagnostics import export_diagnostics
from analytics.metrics import compute_metrics
from analytics.metrics_accumulator import SignoffMetricsAccumulator
from analytics.parallel_sweep import resolve_sweep_workers, run_games_parallel
from analytics.stats import min_sample_size
from engine.cards import compute_card_set_version, load_all_cards, load_config


def run_sweep(
    config_path: str,
    games: int | None = None,
    seed: int = 0,
    *,
    metrics_mode: str = "full",
    workers: int | None = None,
    skip_diagnostics: bool = False,
    skip_replay: bool = False,
) -> dict:
    config = load_config(config_path)
    assert not config.get("reward_shaping", False), "reward_shaping must be false in sweeps"
    min_n = min_sample_size(margin=0.05)
    games = games or max(min_n, int(config.get("games_per_cell", min_n)))
    card_version = compute_card_set_version(load_all_cards())
    seat_bots = resolve_seat_bots(config)

    _, acc, logs = run_games_parallel(
        config, games, seed, workers=workers, metrics_mode=metrics_mode
    )

    if metrics_mode == "signoff" and acc is not None:
        metrics = acc.to_metrics()
        diagnostics_path = ""
    else:
        assert logs is not None
        metrics = compute_metrics(logs)
        diagnostics_path = Path("game_logs/diagnostics.json")
        if not skip_diagnostics:
            export_diagnostics(logs, diagnostics_path)
        else:
            diagnostics_path = ""

        if not skip_replay and logs:
            replay_path = Path("viewer/public/replay/sample.json")
            replay_path.parent.mkdir(parents=True, exist_ok=True)
            replay_path.write_text(json.dumps(logs[-1], indent=2), encoding="utf-8")

    result = {
        "config": config,
        "games_run": games,
        "min_recommended_n": min_n,
        "card_set_version": card_version,
        "seat_bots": seat_bots,
        "bot_mode": "league_heuristic",
        "bot_rotation": "seat_bots rotated per game (offset = game_index % num_players)",
        "sweep_workers": workers if workers is not None else resolve_sweep_workers(config),
        "metrics_mode": metrics_mode,
        "metrics": metrics,
        "diagnostics_path": str(diagnostics_path) if diagnostics_path else "",
    }
    return result


def run_sweep_fast(
    config: dict,
    games: int,
    seed: int = 0,
    *,
    workers: int | None = None,
) -> dict:
    """Fast signoff-only sweep for parameter grid cells."""
    min_n = min_sample_size(margin=0.05)
    card_version = compute_card_set_version(load_all_cards())
    seat_bots = resolve_seat_bots(config)
    _, acc, _ = run_games_parallel(
        config, games, seed, workers=workers, metrics_mode="signoff"
    )
    assert acc is not None
    return {
        "config": config,
        "games_run": games,
        "min_recommended_n": min_n,
        "card_set_version": card_version,
        "seat_bots": seat_bots,
        "bot_mode": "league_heuristic",
        "metrics_mode": "signoff",
        "sweep_workers": workers if workers is not None else resolve_sweep_workers(config),
        "metrics": acc.to_metrics(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run parameter sweep simulations")
    parser.add_argument("--config", default="configs/balance.yaml")
    parser.add_argument("--games", type=int, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="game_logs/sweep_result.json")
    parser.add_argument("--fast", action="store_true", help="Signoff metrics only, no diagnostics")
    args = parser.parse_args()

    mode = "signoff" if args.fast else "full"
    result = run_sweep(args.config, args.games, args.seed, metrics_mode=mode)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    from analytics.export_viewer_balance import export_viewer_balance
    from analytics.log_store import log_sweep_run

    log_sweep_run(result, bot_mode=result.get("bot_mode", "league_heuristic"))
    if mode == "full":
        export_viewer_balance(args.out)

    print(f"Sweep complete: {result['games_run']} games, card_set={result['card_set_version']}")
    print(f"Bots: {result.get('seat_bots')}")
    print(f"Assisted win rate: {result['metrics']['assisted_win_rate']:.2%}")
    print(f"Shield hit rate: {result['metrics']['shield_hit_rate']:.2%}")
    if result.get("diagnostics_path"):
        print(f"Diagnostics: {result.get('diagnostics_path')}")


if __name__ == "__main__":
    main()
