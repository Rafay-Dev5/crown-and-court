"""Two-stage parameter grid sweep for n_rounds × deck sizes."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml

from analytics.parallel_sweep import resolve_sweep_workers
from analytics.signoff_compare import _score
from analytics.sweeps import run_sweep_fast
from engine.cards import load_config


def _load_grid_config(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _merge_config(base: dict, overrides: dict) -> dict:
    merged = copy.deepcopy(base)
    merged.update(overrides)
    return merged


def _early_stop_impossible(metrics: dict, games_run: int, gates: dict) -> bool:
    """Reject cell if Wilson upper bound cannot pass assisted cap or role band."""
    if games_run < 50:
        return False
    assisted = float(metrics.get("assisted_win_rate", 0))
    role = metrics.get("role_win_rate", {})
    king_wr = float(role.get("started_as_king", 0))
    if assisted > gates.get("assisted_max", 0.12) * 1.5:
        return True
    if king_wr < 0.25 or king_wr > 0.55:
        return True
    return False


def _cell_score(metrics: dict, games_run: int) -> dict:
    return _score(metrics, 385, games_run)


def _run_cell(payload: dict[str, Any]) -> dict[str, Any]:
    base_path = payload["base_config_path"]
    overrides = payload["overrides"]
    games = int(payload["games"])
    seed = int(payload["seed"])
    base = load_config(base_path)
    config = _merge_config(base, overrides)
    result = run_sweep_fast(config, games=games, seed=seed, workers=payload.get("sweep_workers"))
    score = _cell_score(result["metrics"], games)
    return {
        "overrides": overrides,
        "games_run": games,
        "metrics": result["metrics"],
        "score": score,
        "card_set_version": result["card_set_version"],
    }


def run_parameter_grid(
    grid_path: str = "configs/parameter_grid.yaml",
    base_config_path: str = "configs/balance.yaml",
) -> dict[str, Any]:
    spec = _load_grid_config(grid_path)
    base = load_config(base_config_path)
    n_rounds_vals = spec.get("n_rounds", [4, 5, 6, 7])
    king_sizes = spec.get("king_deck_size", [30, 36, 42])
    noble_sizes = spec.get("noble_deck_size", [40, 46, 52])
    screen_games = int(spec.get("screen_games", 100))
    confirm_games = int(spec.get("confirm_games", 385))
    confirm_top_k = int(spec.get("confirm_top_k", 5))
    grid_workers = int(spec.get("grid_workers", 1))
    early_stop = bool(spec.get("early_stop", True))
    seed_base = int(spec.get("seed", 42))

    sweep_workers = resolve_sweep_workers(base)
    cpu = os.cpu_count() or 4
    if grid_workers * sweep_workers > cpu:
        sweep_workers = max(1, cpu // max(1, grid_workers))

    cells = [
        {"n_rounds": nr, "king_deck_size": ks, "noble_deck_size": ns}
        for nr, ks, ns in itertools.product(n_rounds_vals, king_sizes, noble_sizes)
    ]

    screen_payloads = [
        {
            "base_config_path": base_config_path,
            "overrides": c,
            "games": screen_games,
            "seed": seed_base + i * 17,
            "sweep_workers": sweep_workers,
        }
        for i, c in enumerate(cells)
    ]

    screened: list[dict] = []
    if grid_workers <= 1:
        for p in screen_payloads:
            screened.append(_run_cell(p))
    else:
        with ProcessPoolExecutor(max_workers=grid_workers) as pool:
            futures = {pool.submit(_run_cell, p): p for p in screen_payloads}
            for fut in as_completed(futures):
                screened.append(fut.result())

    gates = {"assisted_max": 0.12}
    if early_stop:
        screened = [
            r for r in screened
            if not _early_stop_impossible(r["metrics"], r["games_run"], gates)
        ]

    screened.sort(
        key=lambda r: (
            -r["score"].get("gates_passed", 0),
            -r["metrics"].get("succession_rate", 0),
            r["metrics"].get("assisted_win_rate", 1),
        )
    )
    finalists = screened[:confirm_top_k]

    confirm_payloads = [
        {
            "base_config_path": base_config_path,
            "overrides": f["overrides"],
            "games": confirm_games,
            "seed": seed_base + 9000 + i,
            "sweep_workers": sweep_workers,
        }
        for i, f in enumerate(finalists)
    ]

    confirmed: list[dict] = []
    for p in confirm_payloads:
        confirmed.append(_run_cell(p))

    confirmed.sort(
        key=lambda r: (
            -r["score"].get("gates_passed", 0),
            -r["metrics"].get("succession_rate", 0),
            r["metrics"].get("assisted_win_rate", 1),
        )
    )
    winner = confirmed[0] if confirmed else (screened[0] if screened else None)

    report = {
        "screen_games": screen_games,
        "confirm_games": confirm_games,
        "cells_screened": len(cells),
        "finalists": len(finalists),
        "screen_results": screened,
        "confirm_results": confirmed,
        "winner": winner,
    }

    out = Path("game_logs/parameter_grid_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if winner:
        _apply_winner(base_config_path, winner["overrides"])
        training_path = Path("configs/training.yaml")
        if training_path.exists():
            tcfg = yaml.safe_load(training_path.read_text(encoding="utf-8")) or {}
            tcfg.update({k: winner["overrides"][k] for k in ("n_rounds",) if k in winner["overrides"]})
            training_path.write_text(yaml.dump(tcfg, default_flow_style=False), encoding="utf-8")

    return report


def _apply_winner(base_config_path: str, overrides: dict) -> None:
    path = Path(base_config_path)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg.update(overrides)
    path.write_text(yaml.dump(cfg, default_flow_style=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run parameter grid sweep")
    parser.add_argument("--config", default="configs/parameter_grid.yaml")
    parser.add_argument("--base", default="configs/balance.yaml")
    args = parser.parse_args()
    report = run_parameter_grid(args.config, args.base)
    w = report.get("winner")
    if w:
        print(f"Winner: {w['overrides']} — gates {w['score'].get('gates_passed')}/5")
    else:
        print("No winner selected")
    print("Wrote game_logs/parameter_grid_results.json")


if __name__ == "__main__":
    main()
