"""End-of-round effects tied to status tags (corrupt drip, etc.)."""

from __future__ import annotations

from engine.effects.interpreter import resolve_effect
from engine.rng import GameRNG
from engine.state import GameState

CORRUPT_DRIP_AMOUNT = 100


def apply_status_tick_effects(state: GameState, rng: GameRNG | None = None) -> None:
    """Apply per-round status upkeep before statuses expire in tick_statuses."""
    rng = rng or GameRNG(seed=hash((state.current_round, state.king_seat)) % (2**31))
    for seat_idx in range(state.num_players):
        for status in state.seats[seat_idx].statuses:
            if status.name != "corrupt":
                continue
            ctx = {
                "seat": seat_idx,
                "target_seat": seat_idx,
                "card_id": "status_corrupt_tick",
            }
            effect = {
                "primitive": "gold_transfer",
                "params": {"from": "self", "to": "king", "amount": CORRUPT_DRIP_AMOUNT},
            }
            resolve_effect(state, effect, ctx, rng)
            state.log_event(
                "status_tick",
                status="corrupt",
                seat=seat_idx,
                amount=CORRUPT_DRIP_AMOUNT,
                to_seat=state.king_seat,
            )
