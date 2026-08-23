"""Four distinct table bots for practice and full-game testing."""

from __future__ import annotations

from typing import Any

from agents.heuristic.bots import HEURISTIC_BOTS
from engine.decisions import DecisionType, PendingDecision
from engine.rng import GameRNG
from web.server.game_session import GameSession, HumanAction

BOT_PROFILES: list[tuple[str, str, str]] = [
    ("hoard", "The Hoarder", "Keeps gold, plays economy cards, almost never trades."),
    ("aggressive", "The Aggressor", "Demands gold and plays disruption / betrayal."),
    ("ally_neighbor", "The Diplomat", "Seeks alliances and alliance cards."),
    ("exploit", "The Opportunist", "Accepts cheap deals and plays whatever is convenient."),
]


def unused_bot_profiles(used_keys: set[str]) -> list[tuple[str, str, str]]:
    return [p for p in BOT_PROFILES if p[0] not in used_keys]


def _other_seats(session: GameSession, seat: int) -> list[int]:
    return [s for s in range(session.state.num_players) if s != seat]


def decide_bot_action(bot_key: str, session: GameSession, dec: PendingDecision) -> HumanAction:
    rng = session.rng
    seat = dec.seat
    state = session.state
    _neg_fn, play_fn, choice_fn = HEURISTIC_BOTS.get(bot_key, HEURISTIC_BOTS["exploit"])
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
        indices = play_fn(state, seat, hand)
        cleaned = sorted({int(i) for i in indices if 0 <= int(i) < len(hand)})[:n]
        if len(cleaned) < n:
            for i in range(len(hand)):
                if i not in cleaned:
                    cleaned.append(i)
                if len(cleaned) >= n:
                    break
        return HumanAction(action_type="play", payload={"card_indices": cleaned[:n]})

    if dec.dtype == DecisionType.CHOICE:
        options = dec.context.get("options") or []
        if options:
            chosen = choice_fn(state, seat, options)
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
