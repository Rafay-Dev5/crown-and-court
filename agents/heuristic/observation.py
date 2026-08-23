from __future__ import annotations

import numpy as np

from engine.state import GameState

OBS_DIM = 48
MAX_SEATS = 8
SEAT_EMBED_DIM = MAX_SEATS
GLOBAL_OBS_DIM = OBS_DIM * MAX_SEATS + MAX_SEATS  # stacked local obs + acting-seat one-hot
ACTOR_INPUT_DIM = OBS_DIM + SEAT_EMBED_DIM

CARD_CATEGORIES = (
    "economy",
    "disruption",
    "betrayal",
    "alliance",
    "protection",
    "information",
    "tempo",
    "supercard",
)


def seat_observation(state: GameState, seat: int) -> np.ndarray:
    """Fixed-size observation vector for RL policies (see PROJECT_STATUS.md §3.4)."""
    obs = np.zeros(OBS_DIM, dtype=np.float32)
    person = state.person_at_seat(seat)

    obs[0] = state.current_round / max(1, state.n_rounds)
    obs[1] = 1.0 if seat == state.king_seat else 0.0
    obs[2] = person.gold / 2000.0
    obs[3] = person.earned_gold / 2000.0
    obs[4] = len(state.seats[seat].hand) / 8.0
    obs[5] = 1.0 if state.phase.value == "negotiation" else 0.0
    obs[6] = 1.0 if state.phase.value == "playing" else 0.0

    hand = state.seats[seat].hand
    for idx, category in enumerate(CARD_CATEGORIES):
        count = sum(1 for c in hand if c.get("category") == category)
        obs[7 + idx] = count / 8.0

    for s in range(min(state.num_players, 6)):
        p = state.person_at_seat(s)
        obs[15 + s * 2] = p.gold / 2000.0
        obs[16 + s * 2] = p.earned_gold / 2000.0

    ctx = negotiation_context(state, seat)
    obs[27] = 1.0 if ctx["threat_received"] else 0.0
    obs[28] = 1.0 if ctx["alliance_active"] else 0.0
    obs[29] = 1.0 if ctx["pending_trade_to_self"] else 0.0
    obs[30] = 1.0 if ctx["default_theft_target"] else 0.0

    earned = [state.person_at_seat(s).earned_gold for s in range(state.num_players)]
    rank = sorted(earned).index(person.earned_gold) if earned else 0
    obs[31] = rank / max(1, state.num_players - 1)
    obs[32] = person.gifted_gold / 2000.0

    return obs


def global_observation(state: GameState, acting_seat: int) -> np.ndarray:
    """Centralized critic input: all seats' local views + acting-seat one-hot."""
    obs = np.zeros(GLOBAL_OBS_DIM, dtype=np.float32)
    n = min(state.num_players, MAX_SEATS)
    for s in range(n):
        obs[s * OBS_DIM : (s + 1) * OBS_DIM] = seat_observation(state, s)
    if 0 <= acting_seat < MAX_SEATS:
        obs[OBS_DIM * MAX_SEATS + acting_seat] = 1.0
    return obs


def actor_observation(state: GameState, seat: int) -> np.ndarray:
    """Decentralized actor input: local obs + seat identity embedding."""
    local = seat_observation(state, seat)
    embed = np.zeros(SEAT_EMBED_DIM, dtype=np.float32)
    if 0 <= seat < SEAT_EMBED_DIM:
        embed[seat] = 1.0
    return np.concatenate([local, embed]).astype(np.float32)


def negotiation_context(state: GameState, seat: int) -> dict[str, bool]:
    """Signals from the current round's negotiation for shield / deal heuristics."""
    threat_received = False
    alliance_to_self = False
    pending_trade = False
    for event in state.event_log:
        if event.get("round") != state.current_round:
            continue
        if event["type"] == "threaten" and event.get("target") == seat:
            threat_received = True
        if event["type"] == "propose_alliance":
            targets = event.get("targets") or []
            if seat in targets or event.get("target") == seat:
                alliance_to_self = True
        if event["type"] == "propose_trade" and event.get("target") == seat:
            pending_trade = True

    for proposal in state.pending_proposals:
        if proposal.get("status") != "pending":
            continue
        if proposal.get("type") == "trade" and proposal.get("target") == seat:
            pending_trade = True
        if proposal.get("type") == "alliance":
            targets = proposal.get("targets") or []
            if seat in targets:
                alliance_to_self = True

    alliance_active = any(seat in a.members for a in state.alliances)
    play_nobles = state.noble_play_order()
    default_theft_target = bool(play_nobles and play_nobles[0] == seat)

    return {
        "threat_received": threat_received,
        "alliance_to_self": alliance_to_self,
        "alliance_active": alliance_active,
        "pending_trade_to_self": pending_trade,
        "default_theft_target": default_theft_target,
    }
