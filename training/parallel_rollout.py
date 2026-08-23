"""Parallel episode rollouts for faster training data collection."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from engine.cards import load_config
from engine.rng import GameRNG
from training.episode_runner import run_shared_episode


def _worker_rollout(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload["config"]
    train_seat = int(payload["train_seat"])
    game_index = int(payload["game_index"])
    seed = int(payload["seed"])
    weights_path = payload["weights_path"]
    backend = str(config.get("policy_backend", "numpy"))

    if backend == "torch":
        from training.ctde_policy_torch import TorchSharedGRUPolicy, resolve_device

        policy = TorchSharedGRUPolicy.load(weights_path, device=resolve_device("cpu"))
    else:
        from training.ctde_policy import SharedGRUPolicy

        policy = SharedGRUPolicy.load(weights_path)

    result = run_shared_episode(
        config,
        GameRNG(seed=seed),
        train_seat=train_seat,
        policy=policy,
        league=None,
        game_index=game_index,
        train=True,
        defer_update=True,
    )
    return {
        "won": result["won"],
        "loss": 0.0,
        "reward": result["reward"],
        "train_seat": train_seat,
        "assisted_win": result["assisted_win"],
        "trajectory": result.get("trajectory", []),
    }


def collect_rollouts(
    config: dict[str, Any],
    policy,
    *,
    episodes: int,
    start_episode: int,
    seed: int,
    weights_path: Path,
    workers: int,
) -> list[dict[str, Any]]:
    """Run `episodes` rollouts in parallel worker processes."""
    policy.save(weights_path)
    config_json = json.loads(json.dumps(config))

    payloads = []
    for i in range(episodes):
        ep = start_episode + i
        train_seat = (ep - 1) % int(config.get("num_players", 6))
        payloads.append(
            {
                "config": config_json,
                "train_seat": train_seat,
                "game_index": ep,
                "seed": seed + ep,
                "weights_path": str(weights_path),
            }
        )

    results: list[dict[str, Any]] = []
    if workers <= 1:
        for p in payloads:
            results.append(_worker_rollout(p))
        return results

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_worker_rollout, p) for p in payloads]
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: r.get("train_seat", 0))
    return results
