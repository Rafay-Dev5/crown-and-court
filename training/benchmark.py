from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from analytics.stats import exploitability_estimate, wilson_interval
from engine.cards import load_config
from engine.rng import GameRNG
from training.ctde_policy import SharedGRUPolicy
from training.policy_factory import build_policy, load_policy
from training.episode_runner import run_shared_episode


def _eval_worker(payload: dict[str, Any]) -> int:
    """Run one eval game in a worker process."""
    config = payload["config"]
    weights_path = payload["weights_path"]
    seed = int(payload["seed"])
    train_seat = int(payload["train_seat"])
    opponent_mode = payload["opponent_mode"]
    backend = str(config.get("policy_backend", "numpy")).lower()

    if backend == "torch":
        from training.ctde_policy_torch import TorchSharedGRUPolicy, resolve_device

        policy = TorchSharedGRUPolicy.load(weights_path, device=resolve_device("cpu"))
    else:
        policy = SharedGRUPolicy.load(weights_path)

    result = run_shared_episode(
        config,
        GameRNG(seed=seed),
        train_seat=train_seat,
        policy=policy,
        league=None,
        game_index=seed,
        train=False,
        opponent_mode=opponent_mode,
    )
    return int(result["won"])


def evaluate_policy(
    policy: SharedGRUPolicy,
    config: dict[str, Any],
    games: int,
    seed: int,
    train_seat: int = 0,
    opponent_mode: str = "league",
    *,
    workers: int = 1,
    weights_path: Path | str | None = None,
) -> dict[str, Any]:
    """Win rate for train_seat policy vs a fixed opponent roster."""
    wins = 0
    worker_count = max(1, workers)
    if worker_count > 1 and games > 1 and weights_path is not None:
        policy.save(weights_path)
        config_json = json.loads(json.dumps(config))
        payloads = [
            {
                "config": config_json,
                "weights_path": str(weights_path),
                "seed": seed + i,
                "train_seat": train_seat,
                "opponent_mode": opponent_mode,
            }
            for i in range(games)
        ]
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures = [pool.submit(_eval_worker, p) for p in payloads]
            for fut in as_completed(futures):
                wins += fut.result()
    else:
        for i in range(games):
            rng = GameRNG(seed=seed + i)
            result = run_shared_episode(
                config,
                rng,
                train_seat=train_seat,
                policy=policy,
                league=None,
                game_index=i,
                train=False,
                opponent_mode=opponent_mode,
            )
            wins += int(result["won"])
    rate = wins / games if games else 0.0
    lo, hi = wilson_interval(wins, games)
    return {
        "games": games,
        "train_seat": train_seat,
        "opponent_mode": opponent_mode,
        "win_rate": rate,
        "win_rate_ci": {"low": lo, "high": hi},
        "wins": wins,
    }


def run_benchmarks(
    policy: SharedGRUPolicy | Any,
    config_path: str = "configs/training.yaml",
    games: int = 100,
    seed: int = 0,
    train_seat: int = 0,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Skill gap vs random baseline and exploitability vs counter roster.

    - skill_gap: league win rate minus fair-share (1/n)
    - exploitability_gap: league win rate minus all-exploit win rate (drop under counter)
    - exploitability: stats.exploitability_estimate(league_wr, 1 - exploit_wr)
    """
    config = config or load_config(config_path)
    assert not config.get("reward_shaping", False), "reward_shaping must be false for benchmarks"
    num_players = int(config.get("num_players", 6))
    fair_share = 1.0 / num_players
    workers = int(config.get("benchmark_workers", 0))
    if workers <= 0:
        workers = 1

    snap = Path("game_logs/training/benchmark_policy_snapshot.json")
    snap.parent.mkdir(parents=True, exist_ok=True)
    eval_kw = dict(workers=workers, weights_path=snap)

    league = evaluate_policy(policy, config, games, seed, train_seat, "league", **eval_kw)
    random_eval = evaluate_policy(policy, config, games, seed + 1000, train_seat, "random", **eval_kw)
    exploit = evaluate_policy(policy, config, games, seed + 2000, train_seat, "exploit", **eval_kw)

    league_wr = float(league["win_rate"])
    random_wr = float(random_eval["win_rate"])
    exploit_wr = float(exploit["win_rate"])

    skill_gap = league_wr - fair_share
    skill_gap_vs_random = league_wr - random_wr
    exploitability_gap = league_wr - exploit_wr
    exploitability = exploitability_estimate(league_wr, 1.0 - exploit_wr)

    result = {
        "games_per_eval": games,
        "train_seat": train_seat,
        "fair_share_win_rate": fair_share,
        "benchmark_workers": workers,
        "league_eval": league,
        "random_eval": random_eval,
        "exploit_eval": exploit,
        "skill_gap": skill_gap,
        "skill_gap_vs_random": skill_gap_vs_random,
        "exploitability_gap": exploitability_gap,
        "exploitability": exploitability,
        "interpretation": {
            "skill_gap": "League win rate minus fair 1/n — higher means policy beats par.",
            "skill_gap_vs_random": "League win rate minus win rate vs all-random opponents.",
            "exploitability_gap": "League WR minus all-exploit WR. Positive = policy wins more vs mixed league than vs all-exploit seats (exploit roster is relatively harder). Negative = all-exploit is easier (common: exploit bot accepts trades and plays safe-random).",
            "exploitability": "max(0, (1 - exploit_WR) - league_WR). Opponent-strength proxy from stats.exploitability_estimate — not a CFR exploitability bound.",
            "exploit_roster_note": "exploit mode sets every opponent seat to the `exploit` heuristic bot, not a computed best response.",
        },
    }
    return result


def write_benchmark_report(result: dict[str, Any], path: Path | str = "game_logs/training/benchmark.json") -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Skill-gap and exploitability benchmarks")
    parser.add_argument("--config", default="configs/training.yaml")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--checkpoint", default="", help="Optional frozen policy JSON")
    parser.add_argument("--out", default="game_logs/training/benchmark.json")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.checkpoint:
        policy = load_policy(args.checkpoint, config)
    else:
        policy = build_policy(config, seed=args.seed)

    result = run_benchmarks(policy, args.config, args.games, args.seed, config=config)
    path = write_benchmark_report(result, args.out)
    print(json.dumps(result, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
