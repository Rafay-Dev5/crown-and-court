"""End-of-phase resolution for protection bets (guess-right / guess-wrong)."""

from __future__ import annotations

from engine.effects.primitives import _evaluate_trigger
from engine.rng import GameRNG
from engine.state import GameState


def finalize_protection_bets(state: GameState, rng: GameRNG) -> None:
    """Resolve armed shields: hit if trigger matched phase events, whiff otherwise."""
    from engine.effects.interpreter import resolve_on_whiff_penalty

    for bet in state.pending_protection_bets:
        ctx: dict = {
            "seat": bet.seat,
            "card_id": bet.card_id,
            "target_seat": bet.target_seat,
            "card": bet.card,
        }
        trigger_type = bet.trigger.get("type", bet.trigger.get("trigger_type", ""))
        attacks_on_self = sum(
            1
            for atk in state.phase_attacks
            if atk.target_seat == bet.seat and not atk.blocked
        )
        if _evaluate_trigger(state, bet.trigger, ctx):
            state.log_event(
                "protection_hit",
                seat=bet.seat,
                card_id=bet.card_id,
                trigger_type=trigger_type,
                attacks_on_self=attacks_on_self,
                resolution="deferred",
            )
        else:
            state.active_shields = [
                s
                for s in state.active_shields
                if not (s.seat == bet.seat and s.card_id == bet.card_id and not s.consumed)
            ]
            ctx["whiff_reason"] = "no_matching_attack"
            ctx["trigger_type"] = trigger_type
            ctx["attacks_on_self"] = attacks_on_self
            ctx["resolution"] = "deferred"
            resolve_on_whiff_penalty(state, bet.card, ctx, rng)
    state.pending_protection_bets.clear()
