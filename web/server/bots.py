"""Four distinct table bots for practice and full-game testing.

Kept free of the RL ``agents`` package so the slim Railway image can import
this module without numpy / agents/ being present.
"""

from __future__ import annotations

from typing import Any

from engine.decisions import DecisionType, PendingDecision
from engine.phases import random_choice_policy, random_play_policy
from engine.rng import GameRNG
from web.server.game_session import GameSession, HumanAction

BOT_PROFILES: list[tuple[str, str, str]] = [
    ("hoard", "The Hoarder", "Keeps gold, plays economy cards, almost never trades."),
    ("aggressive", "The Aggressor", "Demands gold and plays disruption / betrayal."),
    ("ally_neighbor", "The Diplomat", "Seeks alliances and alliance cards."),
    ("exploit", "The Opportunist", "Accepts cheap deals and plays whatever is convenient."),
]

_PLAY_PREF: dict[str, tuple[str, ...]] = {
    "hoard": ("economy", "protection", "tempo"),
    "aggressive": ("disruption", "betrayal", "information"),
    "ally_neighbor": ("alliance", "economy", "protection"),
    "exploit": ("economy", "disruption", "betrayal", "alliance"),
}


def unused_bot_profiles(used_keys: set[str]) -> list[tuple[str, str, str]]:
    return [p for p in BOT_PROFILES if p[0] not in used_keys]


def _other_seats(session: GameSession, seat: int) -> list[int]:
    return [s for s in range(session.state.num_players) if s != seat]


def _pick_play_indices(bot_key: str, hand: list[dict], n: int) -> list[int]:
    prefs = _PLAY_PREF.get(bot_key, ())
    ranked: list[int] = []
    for cat in prefs:
        for i, card in enumerate(hand):
            if i not in ranked and card.get("category") == cat:
                ranked.append(i)
            if len(ranked) >= n:
                return ranked[:n]
    for i in range(len(hand)):
        if i not in ranked:
            ranked.append(i)
        if len(ranked) >= n:
            break
    return ranked[:n]


def _pick_choice(bot_key: str, session: GameSession, seat: int, options: list[dict]) -> str:
    if not options:
        return ""
    if len(options) == 1:
        return str(options[0].get("id", ""))

    risky = ("invest_private", "private", "bold", "double", "steal", "backstab", "coup")
    safe = ("invest_public", "public", "safe", "conservative", "ward")

    def score(opt: dict, idx: int) -> float:
        oid = str(opt.get("id", "")).lower()
        label = str(opt.get("label", "")).lower()
        text = f"{oid} {label}"
        s = 0.0
        if bot_key == "aggressive":
            if any(k in text for k in risky):
                s += 3.0
            s += idx * 0.2
        elif bot_key == "hoard":
            if any(k in text for k in safe):
                s += 3.0
            if "public" in text:
                s += 1.5
            s -= idx * 0.2
        elif bot_key == "ally_neighbor":
            if "public" in text or "alliance" in text or "pact" in text:
                s += 2.5
        return s

    scored = [(score(opt, i), str(opt.get("id", ""))) for i, opt in enumerate(options)]
    best = max(scored, key=lambda x: x[0])[0]
    top = [oid for val, oid in scored if val >= best - 0.01 and oid]
    if not top:
        return random_choice_policy(session.state, seat, options)
    rng = GameRNG(seed=hash((bot_key, seat, session.state.current_round, tuple(top))) % (2**31))
    return rng.choice(top)


def decide_bot_action(bot_key: str, session: GameSession, dec: PendingDecision) -> HumanAction:
    rng = session.rng
    seat = dec.seat
    state = session.state
    others = _other_seats(session, seat)

    if dec.dtype == DecisionType.NEGOTIATION:
        if bot_key == "hoard" or not others:
            return HumanAction(action_type="pass")
        target = others[rng.randint(0, len(others) - 1)] if others else seat
        if bot_key == "ally_neighbor":
            neighbor = (seat + 1) % state.num_players
            if state.has_alliance_between(seat, neighbor):
                return HumanAction(action_type="pass")
            return HumanAction(
                action_type="propose_alliance",
                payload={"targets": [neighbor], "terms": "neighbor pact"},
            )
        if bot_key == "aggressive":
            if state.has_status(target, "oathbreaker"):
                return HumanAction(action_type="pass")
            amount = int(rng.randint(20, 35))
            return HumanAction(
                action_type="propose_trade",
                payload={
                    "target": target,
                    "offer": {"gold": 0},
                    "request": {"gold": amount},
                },
            )
        if bot_key == "exploit" and rng.random() < 0.35:
            return HumanAction(
                action_type="propose_trade",
                payload={
                    "target": target,
                    "offer": {"gold": 20},
                    "request": {"gold": 20},
                },
            )
        return HumanAction(action_type="pass")

    if dec.dtype == DecisionType.PLAY:
        hand = state.seats[seat].hand
        n = int(dec.context.get("n_play", 2))
        cleaned = _pick_play_indices(bot_key, hand, n)
        if len(cleaned) < n:
            fallback = random_play_policy(state, seat, hand)
            for i in fallback:
                if i not in cleaned:
                    cleaned.append(i)
                if len(cleaned) >= n:
                    break
        return HumanAction(action_type="play", payload={"card_indices": cleaned[:n]})

    if dec.dtype == DecisionType.CHOICE:
        options = dec.context.get("options") or []
        if options:
            chosen = _pick_choice(bot_key, session, seat, options)
            for i, opt in enumerate(options):
                if opt.get("id") == chosen:
                    return HumanAction(action_type="choice", payload={"choice_index": i})
        return HumanAction(action_type="choice", payload={"choice_index": 0})

    return HumanAction(action_type="pass")


def bot_should_accept(bot_key: str, proposal: dict[str, Any], rng: GameRNG) -> bool:
    ptype = proposal.get("type")
    if bot_key == "hoard":
        return False
    if bot_key == "ally_neighbor":
        return ptype == "alliance"
    if bot_key == "aggressive":
        if ptype == "trade":
            offer = int((proposal.get("offer") or {}).get("gold", 0) or 0)
            request = int((proposal.get("request") or {}).get("gold", 0) or 0)
            return offer >= request
        return rng.random() > 0.7
    if ptype == "trade":
        request = int((proposal.get("request") or {}).get("gold", 0) or 0)
        return request <= 40
    return rng.random() > 0.4
