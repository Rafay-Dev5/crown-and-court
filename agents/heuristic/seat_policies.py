from __future__ import annotations

from typing import Any, Callable

from agents.heuristic.bots import get_bot
from engine.negotiation import random_negotiation_policy
from engine.phases import random_choice_policy, random_play_policy
from engine.rng import GameRNG
from engine.state import GameState

NegotiationFn = Callable[[GameState, int, GameRNG], None]
PlayFn = Callable[[GameState, int, list[dict]], list[int]]
ChoiceFn = Callable[[GameState, int, list[dict]], str]

DEFAULT_SEAT_BOTS = ["hoard", "aggressive", "ally_neighbor", "exploit", "hoard", "aggressive"]


def resolve_seat_bots(config: dict[str, Any], opponent_mode: str | None = None) -> list[str]:
    n = int(config.get("num_players", 6))
    if opponent_mode == "random":
        return ["random"] * n
    if opponent_mode == "exploit":
        return ["exploit"] * n
    if opponent_mode == "league":
        return resolve_seat_bots({**config, "seat_bots": None})
    if config.get("seat_bots"):
        bots = list(config["seat_bots"])
        while len(bots) < n:
            bots.append(bots[len(bots) % max(1, len(config["seat_bots"]))])
        return bots[:n]
    league = config.get("league_bots", DEFAULT_SEAT_BOTS)
    return [league[i % len(league)] for i in range(n)]


def build_seat_bot_fns(
    config: dict[str, Any],
    seat_bots: list[str] | None = None,
    opponent_mode: str | None = None,
) -> list[tuple[NegotiationFn, PlayFn, ChoiceFn]]:
    if seat_bots is not None:
        names = seat_bots
    else:
        names = resolve_seat_bots(config, opponent_mode=opponent_mode)
    return [get_bot(name) for name in names]
