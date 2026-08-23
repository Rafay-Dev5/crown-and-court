from __future__ import annotations

from typing import Any

from engine.effects.primitives import PRIMITIVE_REGISTRY, _evaluate_trigger
from engine.rng import GameRNG
from engine.shields import whiff_penalty_scale
from engine.state import GameState, PendingChoice

DEFERRED_TRIGGER_TYPES = frozenset({"attacked_this_phase", "attacker_is", "succession_imminent"})


def is_deferred_protection_trigger(trigger: dict | None) -> bool:
    if not trigger:
        return False
    ttype = trigger.get("type", trigger.get("trigger_type", ""))
    return ttype in DEFERRED_TRIGGER_TYPES


def card_preconditions_met(
    state: GameState, card: dict[str, Any], seat: int, target_seat: int | None = None
) -> bool:
    requires = card.get("requires_state") or {}
    if requires.get("alliance_declared_with_target"):
        target = target_seat if target_seat is not None else requires.get("target_seat")
        if target is None:
            return False
        if not state.has_alliance_between(seat, target):
            return False
    if "prior_choice" in requires:
        within = int(requires.get("within_rounds", 3))
        if not state.prior_choice_within(seat, requires["prior_choice"], within):
            return False
    if "target_prior_choice" in requires:
        target = target_seat if target_seat is not None else requires.get("target_seat", seat)
        within = int(requires.get("within_rounds", 3))
        if not state.prior_choice_within(target, requires["target_prior_choice"], within):
            return False
    return True


def resolve_effect(
    state: GameState,
    effect: dict[str, Any],
    ctx: dict[str, Any],
    rng: GameRNG,
    *,
    scale: float = 1.0,
) -> None:
    primitive = effect.get("primitive")
    if not primitive:
        return
    fn = PRIMITIVE_REGISTRY.get(primitive)
    if not fn:
        state.log_event("unknown_primitive", primitive=primitive)
        return
    merged_ctx = {**ctx, "params": dict(effect.get("params") or {}), "effect_scale": scale}
    if scale != 1.0 and "amount" in merged_ctx["params"]:
        merged_ctx["params"]["amount"] = int(merged_ctx["params"]["amount"] * scale)
    fn(state, merged_ctx, rng)
    secondary = effect.get("secondary_effect")
    if secondary:
        resolve_effect(state, secondary, ctx, rng, scale=scale)


def resolve_on_whiff_penalty(
    state: GameState,
    card: dict[str, Any],
    ctx: dict[str, Any],
    rng: GameRNG,
) -> None:
    penalty = card.get("on_whiff_penalty")
    if not penalty:
        params = (card.get("effect") or {}).get("params") or {}
        if params.get("default_whiff_penalty"):
            penalty = params["default_whiff_penalty"]
    if not penalty:
        state.log_event("protection_whiff", seat=ctx["seat"], card_id=card.get("id"), penalty="none")
        return
    scale = whiff_penalty_scale(card)
    extra = {k: ctx[k] for k in ("whiff_reason", "trigger_type", "attacks_on_self", "resolution") if k in ctx}
    state.log_event(
        "protection_whiff",
        seat=ctx["seat"],
        card_id=card.get("id"),
        penalty_scale=scale,
        **extra,
    )
    resolve_effect(state, penalty, ctx, rng, scale=scale)


def resolve_card(
    state: GameState,
    card: dict[str, Any],
    seat: int,
    rng: GameRNG,
    *,
    target_seat: int | None = None,
    selected_choice: str | None = None,
) -> bool:
    """Resolve a card's effect. Returns False if waiting on player choice."""
    if not card_preconditions_met(state, card, seat, target_seat):
        state.log_event("card_precondition_failed", card_id=card.get("id"), seat=seat)
        return True

    ctx: dict[str, Any] = {
        "seat": seat,
        "card_id": card.get("id", ""),
        "target_seat": target_seat if target_seat is not None else seat,
        "card": card,
    }
    if selected_choice:
        ctx["selected_choice"] = selected_choice

    effect = card.get("effect") or {}
    timing = card.get("timing", "on_reveal")
    category = card.get("category", "")
    params = effect.get("params") or {}
    trigger = params.get("trigger")

    is_protection = category == "protection" or timing == "reactive" or trigger

    if is_protection and trigger:
        if is_deferred_protection_trigger(trigger):
            resolve_effect(state, effect, ctx, rng)
            from engine.state import PendingProtectionBet

            state.pending_protection_bets.append(
                PendingProtectionBet(
                    seat=seat,
                    card_id=card.get("id", ""),
                    card=card,
                    trigger=trigger,
                    target_seat=ctx["target_seat"],
                )
            )
        elif _evaluate_trigger(state, trigger, ctx):
            state.log_event("protection_hit", seat=seat, card_id=card.get("id"))
            resolve_effect(state, effect, ctx, rng)
        else:
            resolve_on_whiff_penalty(state, card, ctx, rng)
    else:
        resolve_effect(state, effect, ctx, rng)

    if state.pending_choice and state.pending_choice.seat == seat:
        return False
    return True
