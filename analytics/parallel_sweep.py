"""Parallel heuristic balance sweeps."""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

from agents.heuristic.bots import get_bot
from agents.heuristic.seat_policies import resolve_seat_bots
from analytics.metrics_accumulator import SignoffMetricsAccumulator, extract_game_summary
from engine.phases import run_game
from engine.rng import GameRNG


def _run_one_game(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload["config"]
    seed = int(payload["seed"])
    game_index = int(payload["game_index"])
    seat_bots = payload["seat_bots"]
    num_players = int(config.get("num_players", 6))
    metrics_mode = payload.get("metrics_mode", "full")

    offset = game_index % num_players
    rotated_bots = seat_bots[offset:] + seat_bots[:offset]
    bot_fns = [get_bot(name) for name in rotated_bots]

    def negotiation_policy(state, seat, rng_inner):
        bot_fns[seat][0](state, seat, rng_inner)

    def play_policy(state, seat, hand):
        return bot_fns[seat][1](state, seat, hand)

    def choice_policy(state, seat, options):
        return bot_fns[seat][2](state, seat, options)

    state = run_game(
        config,
        GameRNG(seed=seed),
        negotiation_policy=negotiation_policy,
        play_policy=play_policy,
        choice_policy=choice_policy,
    )
    if metrics_mode == "signoff":
        return extract_game_summary(state.event_log)
    return {"event_log": state.event_log}


def resolve_sweep_workers(config: dict[str, Any]) -> int:
    raw = int(config.get("sweep_workers", 0))
    if raw > 0:
        return min(16, raw)
    return max(1, min(16, (os.cpu_count() or 4) - 1))


def run_games_parallel(
    config: dict[str, Any],
    games: int,
    seed: int,
    *,
    workers: int | None = None,
    metrics_mode: str = "signoff",
) -> tuple[list[dict[str, Any]], SignoffMetricsAccumulator | None, list[list[dict]] | None]:
    """Run games in parallel; return summaries or full logs."""
    worker_count = workers if workers is not None else resolve_sweep_workers(config)
    seat_bots = resolve_seat_bots(config)
    config_json = json.loads(json.dumps(config))

    payloads = [
        {
            "config": config_json,
            "seed": seed + i,
            "game_index": i,
            "seat_bots": seat_bots,
            "metrics_mode": metrics_mode,
        }
        for i in range(games)
    ]

    results: list[dict[str, Any]] = []
    if worker_count <= 1 or games <= 1:
        for p in payloads:
            results.append(_run_one_game(p))
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures = [pool.submit(_run_one_game, p) for p in payloads]
            for fut in as_completed(futures):
                results.append(fut.result())

    if metrics_mode == "signoff":
        acc = SignoffMetricsAccumulator()
        for s in results:
            acc.add(s)
        return results, acc, None

    logs = [r["event_log"] for r in results if "event_log" in r]
    return results, None, logs
