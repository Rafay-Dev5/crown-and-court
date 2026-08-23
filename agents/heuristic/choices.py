from __future__ import annotations

from engine.phases import random_choice_policy
from engine.rng import GameRNG
from engine.state import GameState

RISKY_IDS = ("invest_private", "private", "bold", "double", "steal", "backstab", "coup")
SAFE_IDS = ("invest_public", "public", "safe", "conservative", "ward")


def _score_option(option: dict, bot_name: str, trailing: bool, leading: bool) -> float:
    oid = str(option.get("id", "")).lower()
    label = str(option.get("label", "")).lower()
    text = f"{oid} {label}"
    score = 0.0

    if bot_name == "aggressive" or (bot_name == "exploit" and trailing):
        if any(k in text for k in RISKY_IDS):
            score += 3.0
        if "gain" in label or "steal" in label:
            score += 1.0
    elif bot_name == "hoard" or (bot_name == "exploit" and leading):
        if any(k in text for k in SAFE_IDS):
            score += 3.0
        if "public" in text:
            score += 1.5
    elif bot_name == "ally_neighbor":
        if "public" in text or "alliance" in text or "pact" in text:
            score += 2.5
    elif bot_name == "random":
        return 0.0

    if bot_name == "exploit" and not trailing and not leading:
        score += 0.5 * len(text)

    # Slight preference for higher-index options when aggressive, lower when hoard
    idx_bonus = option.get("_idx", 0)
    if bot_name in ("aggressive",) or (bot_name == "exploit" and trailing):
        score += idx_bonus * 0.2
    elif bot_name == "hoard":
        score -= idx_bonus * 0.2

    return score


def smart_choice_policy(
    state: GameState,
    seat: int,
    options: list[dict],
    bot_name: str = "hoard",
    rng: GameRNG | None = None,
) -> str:
    if not options:
        return ""
    if len(options) == 1:
        return options[0]["id"]

    person = state.person_at_seat(seat)
    king_earned = state.king_earned_gold()
    trailing = person.earned_gold < king_earned * 0.75
    leading = person.earned_gold > king_earned * 1.1

    if bot_name == "random":
        return random_choice_policy(state, seat, options)

    scored = []
    for i, opt in enumerate(options):
        opt_copy = {**opt, "_idx": i}
        scored.append((_score_option(opt_copy, bot_name, trailing, leading), opt["id"]))

    best = max(scored, key=lambda x: x[0])[0]
    top = [oid for s, oid in scored if s >= best - 0.01]
    if len(top) == 1:
        return top[0]

    if rng is None:
        rng = GameRNG(seed=hash((seat, state.current_round, tuple(top))) % (2**31))
    return rng.choice(top)


def make_choice_fn(bot_name: str):
    def fn(state: GameState, seat: int, options: list[dict]) -> str:
        rng = GameRNG(seed=hash((bot_name, seat, state.current_round, len(options))) % (2**31))
        return smart_choice_policy(state, seat, options, bot_name, rng)

    return fn
