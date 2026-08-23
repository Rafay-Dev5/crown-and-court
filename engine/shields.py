from __future__ import annotations

from engine.state import ActiveShield, GameState, PhaseAttack


ATTACK_PRIMITIVES = frozenset({"gold_transfer", "steal_card", "force_discard", "gold_loss"})


def register_shield(state: GameState, shield: ActiveShield) -> None:
    state.active_shields.append(shield)
    state.log_event(
        "shield_registered",
        seat=shield.seat,
        card_id=shield.card_id,
        blocks=shield.blocks,
        specificity=shield.specificity,
    )


def check_and_consume_shield(
    state: GameState,
    target_seat: int,
    attack_type: str,
    attacker_seat: int,
    amount: int = 0,
) -> bool:
    """Return True if attack is blocked by an active shield."""
    single_use_default = state.config.get("shield_single_use", True)
    for shield in state.active_shields:
        if shield.consumed or shield.seat != target_seat:
            continue
        if shield.blocks != "generic" and shield.blocks != attack_type:
            continue
        if shield.targeted_attacker is not None and shield.targeted_attacker != attacker_seat:
            continue
        if shield.amount and amount > shield.amount:
            continue
        if single_use_default and shield.single_use:
            shield.consumed = True
        state.log_event(
            "shield_blocked",
            target=target_seat,
            attacker=attacker_seat,
            attack_type=attack_type,
            card_id=shield.card_id,
        )
        return True
    return False


def log_attack(
    state: GameState,
    attacker_seat: int,
    target_seat: int,
    attack_type: str,
    amount: int = 0,
    blocked: bool = False,
) -> None:
    state.phase_attacks.append(
        PhaseAttack(
            attacker_seat=attacker_seat,
            target_seat=target_seat,
            attack_type=attack_type,
            amount=amount,
            blocked=blocked,
        )
    )


def whiff_penalty_scale(card: dict) -> float:
    """Targeted guesses carry full penalty; generic self-shields carry reduced penalty."""
    params = (card.get("effect") or {}).get("params") or {}
    specificity = params.get("specificity", "generic")
    if specificity == "targeted":
        return float(params.get("penalty_scale", 1.0))
    return float(params.get("penalty_scale", 0.25))
