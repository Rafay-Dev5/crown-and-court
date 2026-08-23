from __future__ import annotations

from typing import Callable

from agents.heuristic.choices import make_choice_fn
from agents.heuristic.observation import negotiation_context, seat_observation
from engine.negotiation import (
    accept_proposal,
    pass_action,
    propose_alliance,
    propose_trade,
    random_negotiation_policy,
)
from engine.phases import random_choice_policy, random_play_policy
from engine.rng import GameRNG
from engine.state import GameState

NegotiationFn = Callable[[GameState, int, GameRNG], None]
PlayFn = Callable[[GameState, int, list[dict]], list[int]]
ChoiceFn = Callable[[GameState, int, list[dict]], str]

__all__ = ["seat_observation", "get_bot", "HEURISTIC_BOTS"]


def _proposal_targets_seat(proposal: dict, seat: int) -> bool:
    if proposal.get("target") == seat:
        return True
    targets = proposal.get("targets") or []
    return seat in targets


def _pending_for_seat(state: GameState, seat: int) -> list[dict]:
    return [
        p
        for p in state.pending_proposals
        if p.get("status") == "pending" and _proposal_targets_seat(p, seat)
    ]


def _plays_per_round(state: GameState, seat: int) -> int:
    return 3 if seat == state.king_seat else 2


def _reactive_protect_gold_indices(hand: list[dict]) -> list[int]:
    """Reactive protect_gold only — excludes miscategorized on_reveal filler cards."""
    indices: list[int] = []
    for i, card in enumerate(hand):
        if card.get("timing") != "reactive":
            continue
        effect = card.get("effect") or {}
        if effect.get("primitive") != "protect_gold":
            continue
        indices.append(i)
    return indices


def _should_play_protection(state: GameState, seat: int) -> bool:
    if state.was_attacked_this_phase(seat):
        return True
    ctx = negotiation_context(state, seat)
    if seat == state.king_seat:
        return bool(ctx["threat_received"])
    # First noble in play order — theft cards usually target them later this phase.
    return bool(ctx["default_theft_target"])


def _eligible_play_indices(state: GameState, seat: int, hand: list[dict]) -> list[int]:
    """Indices safe to pick at random — skip reactive shields unless heuristic says play them."""
    if _should_play_protection(state, seat):
        return list(range(len(hand)))
    blocked = set(_reactive_protect_gold_indices(hand))
    return [i for i in range(len(hand)) if i not in blocked]


def _safe_random_play(state: GameState, seat: int, hand: list[dict]) -> list[int]:
    n = _plays_per_round(state, seat)
    eligible = _eligible_play_indices(state, seat, hand)
    if not eligible:
        return []
    rng = GameRNG(seed=hash((seat, state.current_round, len(hand), "safe")) % (2**31))
    rng.shuffle(eligible)
    return sorted(eligible[:n])


def _merge_protection_plays(state: GameState, seat: int, hand: list[dict], base: list[int]) -> list[int]:
    n = _plays_per_round(state, seat)
    if not _should_play_protection(state, seat):
        return base[:n]
    protection = _reactive_protect_gold_indices(hand)
    if not protection:
        return base[:n]
    # At most one protection bet per round — avoids stacking whiffs on the same phase.
    merged: list[int] = [protection[0]]
    for idx in base:
        if idx not in merged and idx < len(hand):
            merged.append(idx)
        if len(merged) >= n:
            break
    return merged[:n]


def hoard_gold_negotiation(state: GameState, seat: int, rng: GameRNG) -> None:
    pass_action(state, seat)


def hoard_gold_play(state: GameState, seat: int, hand: list[dict]) -> list[int]:
    economy = [i for i, c in enumerate(hand) if c.get("category") == "economy"]
    base = economy[: _plays_per_round(state, seat)] if economy else _safe_random_play(state, seat, hand)
    return _merge_protection_plays(state, seat, hand, base)


def aggressive_negotiation(state: GameState, seat: int, rng: GameRNG) -> None:
    others = [s for s in range(state.num_players) if s != seat]
    if not others:
        pass_action(state, seat)
        return
    person = state.person_at_seat(seat)
    avg_gold = sum(state.person_at_seat(s).gold for s in range(state.num_players)) / state.num_players
    if person.gold > avg_gold * 1.05 and rng.random() < 0.65:
        pass_action(state, seat)
        return
    target = rng.choice(others)
    if state.has_status(target, "oathbreaker"):
        pass_action(state, seat)
        return
    amount = rng.randint(20, 35)
    propose_trade(state, seat, target, {"gold": 0}, {"gold": amount})


def aggressive_play(state: GameState, seat: int, hand: list[dict]) -> list[int]:
    disruption = [i for i, c in enumerate(hand) if c.get("category") in ("disruption", "betrayal")]
    n = _plays_per_round(state, seat)
    base = disruption[:n] if disruption else _safe_random_play(state, seat, hand)
    return _merge_protection_plays(state, seat, hand, base)


def ally_neighbor_negotiation(state: GameState, seat: int, rng: GameRNG) -> None:
    neighbor = (seat + 1) % state.num_players
    if neighbor != seat:
        propose_alliance(state, seat, [neighbor], terms="neighbor pact")
    else:
        pass_action(state, seat)


def ally_neighbor_play(state: GameState, seat: int, hand: list[dict]) -> list[int]:
    alliance = [i for i, c in enumerate(hand) if c.get("category") == "alliance"]
    n = _plays_per_round(state, seat)
    base = alliance[: min(len(alliance), n)] if alliance else _safe_random_play(state, seat, hand)
    return _merge_protection_plays(state, seat, hand, base)


def exploit_negotiation(state: GameState, seat: int, rng: GameRNG) -> None:
    for proposal in _pending_for_seat(state, seat):
        if proposal.get("type") == "trade":
            req_gold = int(proposal.get("request", {}).get("gold", 0))
            proposer_gold = state.person_at_seat(proposal["proposer"]).gold
            if req_gold <= max(1, proposer_gold * 0.10) and rng.random() > 0.55:
                accept_proposal(state, seat, proposal["id"])
                return
        elif proposal.get("type") == "alliance" and rng.random() > 0.55:
            accept_proposal(state, seat, proposal["id"])
            return
    if rng.random() < 0.25:
        random_negotiation_policy(state, seat, rng)
    else:
        pass_action(state, seat)


def exploit_play(state: GameState, seat: int, hand: list[dict]) -> list[int]:
    base = _safe_random_play(state, seat, hand)
    return _merge_protection_plays(state, seat, hand, base)


HEURISTIC_BOTS: dict[str, tuple[NegotiationFn, PlayFn, ChoiceFn]] = {
    "random": (random_negotiation_policy, random_play_policy, random_choice_policy),
    "hoard": (hoard_gold_negotiation, hoard_gold_play, make_choice_fn("hoard")),
    "aggressive": (aggressive_negotiation, aggressive_play, make_choice_fn("aggressive")),
    "ally_neighbor": (ally_neighbor_negotiation, ally_neighbor_play, make_choice_fn("ally_neighbor")),
    "exploit": (exploit_negotiation, exploit_play, make_choice_fn("exploit")),
}


def get_bot(name: str) -> tuple[NegotiationFn, PlayFn, ChoiceFn]:
    return HEURISTIC_BOTS.get(name, HEURISTIC_BOTS["random"])
