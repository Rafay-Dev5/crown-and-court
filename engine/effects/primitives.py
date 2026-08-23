from __future__ import annotations

from typing import Any, Callable

from engine.rng import GameRNG
from engine.shields import check_and_consume_shield, log_attack, register_shield
from engine.state import ActiveShield, ChoiceRecord, DiceRecord, GameState, PendingChoice

EffectContext = dict[str, Any]
EffectFn = Callable[[GameState, EffectContext, GameRNG], None]


def _resolve_target(state: GameState, target: str, ctx: EffectContext) -> int:
    if target == "self":
        return ctx["seat"]
    if target == "king":
        return state.king_seat
    if target == "target":
        return ctx.get("target_seat", ctx["seat"])
    if target.startswith("seat:"):
        return int(target.split(":")[1])
    raise ValueError(f"Unknown target: {target}")


def _resolve_choice_seat(state: GameState, params: dict[str, Any], ctx: EffectContext) -> int:
    """Who makes a dice_swing / prompt_choice decision (default: card player)."""
    which = params.get("choice_seat", "self")
    if which == "target":
        return int(ctx.get("target_seat", ctx["seat"]))
    if which == "king":
        return state.king_seat
    return ctx["seat"]


def gold_gain(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "self"), ctx)
    amount = int(ctx["params"]["amount"])
    person = state.person_at_seat(seat)
    person.gold += amount
    person.earned_gold += amount
    state.log_event("gold_gain", seat=seat, amount=amount, person=person.person_id)


def _evaluate_trigger(state: GameState, trigger: dict, ctx: EffectContext) -> bool:
    seat = ctx["seat"]
    target = ctx.get("target_seat", seat)
    ttype = trigger.get("type", trigger.get("trigger_type", ""))
    if ttype == "attacked_this_phase":
        atk_type = trigger.get("attack_type")
        check_seat = _resolve_target(state, trigger.get("target", "self"), ctx)
        for atk in state.phase_attacks:
            if atk.target_seat == check_seat:
                if atk_type is None or atk.attack_type == atk_type:
                    return True
        return False
    if ttype == "attacker_is":
        expected = int(trigger.get("seat", trigger.get("attacker_seat", -1)))
        for atk in state.phase_attacks:
            if atk.target_seat == seat and atk.attacker_seat == expected and not atk.blocked:
                return True
        return False
    if ttype == "succession_imminent":
        from engine.succession import get_checker

        checker = get_checker(state.config.get("succession_checker", "gold_only"))
        return any(checker(state, s) for s in state.noble_seats())
    if ttype == "always":
        return True
    return False


def gold_loss(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "self"), ctx)
    amount = int(ctx["params"]["amount"])
    attacker = ctx.get("seat", seat)
    if seat != attacker:
        if check_and_consume_shield(state, seat, "gold_theft", attacker, amount):
            log_attack(state, attacker, seat, "gold_theft", amount, blocked=True)
            return
        log_attack(state, attacker, seat, "gold_theft", amount, blocked=False)
    person = state.person_at_seat(seat)
    person.gold = max(0, person.gold - amount)
    person.earned_gold = max(0, person.earned_gold - min(amount, person.earned_gold))
    state.log_event("gold_loss", seat=seat, amount=amount, person=person.person_id)


def gold_transfer(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    params = ctx["params"]
    from_seat = _resolve_target(state, params.get("from", "target"), ctx)
    to_seat = _resolve_target(state, params.get("to", "self"), ctx)
    amount = int(params["amount"])
    is_theft = params.get("as_theft", from_seat != to_seat and to_seat == ctx.get("seat"))
    if is_theft and from_seat != to_seat:
        if check_and_consume_shield(state, from_seat, "gold_theft", to_seat, amount):
            log_attack(state, to_seat, from_seat, "gold_theft", amount, blocked=True)
            betrayer_pays_betrayal_cost(state, ctx, rng, blocked=True)
            return
        log_attack(state, to_seat, from_seat, "gold_theft", amount, blocked=False)
    from_person = state.person_at_seat(from_seat)
    to_person = state.person_at_seat(to_seat)
    transfer = min(amount, from_person.gold)
    from_person.gold -= transfer
    from_person.earned_gold = max(0, from_person.earned_gold - transfer)
    to_person.gold += transfer
    to_person.earned_gold += transfer
    # Gifted/earned split retired — total gold is what matters.
    state.log_event(
        "gold_transfer",
        from_seat=from_seat,
        to_seat=to_seat,
        amount=transfer,
        blocked=False,
    )
    if is_theft:
        betrayer_pays_betrayal_cost(state, ctx, rng, blocked=False)


def betrayer_pays_betrayal_cost(state: GameState, ctx: EffectContext, rng: GameRNG, blocked: bool) -> None:
    """Betrayal social cost lands even when gold transfer is blocked by a shield."""
    card = ctx.get("card") or {}
    if card.get("category") != "betrayal":
        return
    effect = card.get("effect") or {}
    secondary = effect.get("secondary_effect")
    if secondary and blocked:
        state.log_event("betrayal_cost_despite_block", seat=ctx["seat"], card_id=card.get("id"))
        from engine.effects.interpreter import resolve_effect

        resolve_effect(state, secondary, ctx, rng)


def steal_card(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    params = ctx["params"]
    from_seat = _resolve_target(state, params.get("from", "target"), ctx)
    to_seat = _resolve_target(state, params.get("to", "self"), ctx)
    count = int(params.get("count", 1))
    if check_and_consume_shield(state, from_seat, "steal_card", to_seat, count):
        log_attack(state, to_seat, from_seat, "steal_card", count, blocked=True)
        return
    log_attack(state, to_seat, from_seat, "steal_card", count, blocked=False)
    for _ in range(count):
        if not state.seats[from_seat].hand:
            break
        idx = rng.randint(0, len(state.seats[from_seat].hand) - 1)
        card = state.seats[from_seat].hand.pop(idx)
        state.seats[to_seat].hand.append(card)
    state.log_event("steal_card", from_seat=from_seat, to_seat=to_seat, count=count)


def _card_public_summary(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "name": card.get("name"),
        "category": card.get("category"),
        "rarity": card.get("rarity"),
        "effect": card.get("effect"),
        "flavor_text": card.get("flavor_text"),
    }


def force_discard(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "target"), ctx)
    count = int(ctx["params"].get("count", 1))
    attacker = ctx.get("seat", seat)
    if seat != attacker:
        if check_and_consume_shield(state, seat, "force_discard", attacker, count):
            log_attack(state, attacker, seat, "force_discard", count, blocked=True)
            return
        log_attack(state, attacker, seat, "force_discard", count, blocked=False)

    hand = state.seats[seat].hand
    count = min(count, len(hand))
    if count <= 0:
        state.log_event("force_discard", seat=seat, count=0)
        return

    # Interactive tables: victim chooses which cards. Training keeps random.
    if state.config.get("pause_between_reveals"):
        state.pending_discards.append(
            {
                "seat": seat,
                "count": count,
                "attacker": attacker,
                "card_id": ctx.get("card_id"),
            }
        )
        state.log_event("discard_required", seat=seat, count=count)
        return

    discarded = []
    for _ in range(count):
        idx = rng.randint(0, len(state.seats[seat].hand) - 1)
        card = state.seats[seat].hand.pop(idx)
        state.seats[seat].discard.append(card)
        discarded.append(_card_public_summary(card))
    state.log_event("force_discard", seat=seat, count=count, discarded=discarded)


def draw_extra(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    from engine.phases import draw_to_hand

    seat = _resolve_target(state, ctx["params"].get("target", "self"), ctx)
    count = int(ctx["params"].get("count", 1))
    draw_to_hand(state, seat, count, rng)
    state.log_event("draw_extra", seat=seat, count=count)


def peek_card(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    peeker = ctx["seat"]
    target = _resolve_target(state, ctx["params"].get("target", "target"), ctx)
    hand = state.seats[target].hand
    if not hand:
        state.log_event("peek_card", seat=peeker, target_seat=target, empty=True)
        return

    raw_idx = ctx["params"].get("card_index")
    if raw_idx is None or not (0 <= int(raw_idx) < len(hand)):
        idx = rng.randint(0, len(hand) - 1)
    else:
        idx = int(raw_idx)
    seen = _card_public_summary(hand[idx])
    # Only the peeker learns the card identity (via private_peeks / private state).
    state.private_peeks[peeker] = {
        "from_seat": target,
        "card": seen,
        "card_index": idx,
    }
    state.log_event("peek_card", seat=peeker, target_seat=target)


def reveal_hand(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "target"), ctx)
    # Full public summaries so every client can show the revealed hand visually.
    hand_cards = [_card_public_summary(c) for c in state.seats[seat].hand]
    state.log_event(
        "reveal_hand",
        seat=seat,
        cards=hand_cards,
        card_ids=[c.get("id") for c in hand_cards],
    )


def negate_effect(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    state.log_event("negate_effect", params=ctx["params"])


def redirect_effect(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    if "new_target" in ctx["params"]:
        ctx["target_seat"] = _resolve_target(state, ctx["params"]["new_target"], ctx)
    state.log_event("redirect_effect", params=ctx["params"])


def copy_last_effect(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    state.log_event("copy_last_effect", seat=ctx["seat"])


def swap_hands(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    params = ctx["params"]
    a = _resolve_target(state, params.get("player_a", "self"), ctx)
    b = _resolve_target(state, params.get("player_b", "target"), ctx)
    state.seats[a].hand, state.seats[b].hand = state.seats[b].hand, state.seats[a].hand
    state.log_event("swap_hands", seat_a=a, seat_b=b)


def block_succession(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = ctx["seat"]
    duration = int(ctx["params"].get("duration_rounds", 1))
    state.apply_status(seat, "block_succession", duration)
    state.log_event("block_succession", seat=seat, duration=duration)


def protect_gold(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "self"), ctx)
    duration = int(ctx["params"].get("duration_rounds", 1))
    amount = int(ctx["params"].get("amount", 150))
    specificity = ctx["params"].get("specificity", "generic")
    blocks = ctx["params"].get("blocks", "gold_theft")
    targeted = ctx["params"].get("targeted_attacker")
    register_shield(
        state,
        ActiveShield(
            seat=seat,
            card_id=ctx.get("card_id", ""),
            blocks=blocks,
            amount=amount,
            targeted_attacker=int(targeted) if targeted is not None else None,
            specificity=specificity,
            single_use=state.config.get("shield_single_use", True),
            expires_after_round=state.current_round + duration,
        ),
    )
    state.log_event("protect_gold", seat=seat, params=ctx["params"])


def mark_status(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "self"), ctx)
    name = ctx["params"]["status_name"]
    duration = int(ctx["params"].get("duration_rounds", 2))
    state.apply_status(seat, name, duration)
    state.log_event("mark_status", seat=seat, status=name, duration=duration)


def alliance_bonus(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    params = ctx["params"]
    amount = int(params.get("amount", 50))
    members = params.get("players", [])
    if isinstance(members, list) and len(members) == 2:
        a = _resolve_target(state, members[0], ctx)
        b = _resolve_target(state, members[1], ctx)
        if state.has_alliance_between(a, b):
            for seat in (a, b):
                person = state.person_at_seat(seat)
                person.gold += amount
                person.earned_gold += amount
            state.log_event("alliance_bonus", seats=[a, b], amount=amount)


def skip_next_play(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "target"), ctx)
    state.apply_status(seat, "skip_next_play", 1)
    state.log_event("skip_next_play", seat=seat)


def gain_legitimacy(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "self"), ctx)
    amount = int(ctx["params"].get("amount", 1))
    state.person_at_seat(seat).legitimacy += amount
    state.log_event("gain_legitimacy", seat=seat, amount=amount)


def extra_play(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    seat = _resolve_target(state, ctx["params"].get("target", "self"), ctx)
    state.apply_status(seat, "extra_play", 1)
    state.log_event("extra_play", seat=seat, count=ctx["params"].get("count", 1))


def conditional_swing(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    from engine.effects.interpreter import resolve_effect

    params = ctx["params"]
    condition = params.get("condition", {})
    met = _evaluate_condition(state, condition, ctx)
    branch = params.get("effect_if_true") if met else params.get("effect_if_false")
    if branch:
        resolve_effect(state, branch, ctx, rng)


def prompt_choice(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    params = ctx["params"]
    choice_id = params.get("store_as") or params.get("choice_id", "choice")
    if "selected_choice" in ctx:
        state.choice_log.append(
            ChoiceRecord(
                round=state.current_round,
                phase=state.phase.value,
                card_id=ctx.get("card_id", ""),
                choice_id=ctx["selected_choice"],
                seat=ctx["seat"],
            )
        )
        state.log_event(
            "choice_made",
            seat=ctx["seat"],
            choice_id=ctx["selected_choice"],
            card_id=ctx.get("card_id"),
        )
        return

    options = params.get("options", [])
    if not options:
        return
    state.pending_choice = PendingChoice(
        seat=ctx["seat"],
        card_id=ctx.get("card_id", ""),
        options=options,
        callback_key=choice_id,
    )


def roll_die(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    params = ctx["params"]
    sides = int(params.get("sides", 6))
    target_min = int(params.get("target_min", 4))
    roll = rng.randint(1, sides)
    success = roll >= target_min
    state.dice_log.append(
        DiceRecord(
            round=state.current_round,
            phase=state.phase.value,
            card_id=ctx.get("card_id", ""),
            seat=ctx["seat"],
            sides=sides,
            roll=roll,
            target_min=target_min,
            success=success,
        )
    )
    ctx["last_roll"] = roll
    ctx["last_roll_success"] = success
    state.log_event(
        "dice_roll",
        seat=ctx["seat"],
        roll=roll,
        sides=sides,
        target_min=target_min,
        success=success,
        card_id=ctx.get("card_id"),
    )


def dice_swing(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    from engine.effects.interpreter import resolve_effect

    params = ctx["params"]
    chooser = _resolve_choice_seat(state, params, ctx)

    if params.get("choices") and ctx.get("selected_choice"):
        state.choice_log.append(
            ChoiceRecord(
                round=state.current_round,
                phase=state.phase.value,
                card_id=ctx.get("card_id", ""),
                choice_id=ctx["selected_choice"],
                seat=chooser,
            )
        )
        state.log_event(
            "choice_made",
            seat=chooser,
            choice_id=ctx["selected_choice"],
            card_id=ctx.get("card_id"),
        )

    if "selected_choice" not in ctx and params.get("choices"):
        prompt_choice(
            state,
            {
                **ctx,
                "seat": chooser,
                "params": {
                    "options": params["choices"],
                    "store_as": params.get("state_key", "dice_choice"),
                },
            },
            rng,
        )
        if state.pending_choice:
            return

    choice_id = ctx.get("selected_choice")
    branches = params.get("branches", {})
    branch = branches.get(choice_id, {}) if choice_id else {}

    if "die" not in branch:
        effect = branch.get("on_success") or branch.get("effect")
        if effect:
            resolve_effect(state, effect, ctx, rng)
        return

    die_cfg = branch.get("die", params.get("die", {"sides": 6, "target_min": 4}))
    roll_die(state, {**ctx, "params": die_cfg}, rng)
    success = ctx.get("last_roll_success", False)

    effect_key = "on_success" if success else "on_failure"
    effect = branch.get(effect_key) or params.get(effect_key)
    if effect:
        resolve_effect(state, effect, ctx, rng)

    if not success and branch.get("on_failure_status"):
        mark_status(
            state,
            {**ctx, "params": branch["on_failure_status"]},
            rng,
        )


def conditional_on_choice(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    from engine.effects.interpreter import resolve_effect

    params = ctx["params"]
    required = params.get("choice_id")
    within = int(params.get("within_rounds", 3))
    target_seat = _resolve_target(state, params.get("target", "target"), ctx)
    if state.prior_choice_within(target_seat, required, within):
        if params.get("effect_if_match"):
            resolve_effect(state, params["effect_if_match"], ctx, rng)
    elif params.get("effect_if_no_match"):
        resolve_effect(state, params["effect_if_no_match"], ctx, rng)


def on_whiff_penalty(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    """Explicit whiff penalty primitive — usually invoked via card.on_whiff_penalty field."""
    from engine.effects.interpreter import resolve_effect

    inner = ctx["params"].get("effect") or ctx["params"]
    scale = float(ctx.get("effect_scale", 1.0))
    resolve_effect(state, inner, ctx, rng, scale=scale)


def conditional_on_status(state: GameState, ctx: EffectContext, rng: GameRNG) -> None:
    from engine.effects.interpreter import resolve_effect

    params = ctx["params"]
    status = params.get("status_name")
    target_seat = _resolve_target(state, params.get("target", "target"), ctx)
    if state.has_status(target_seat, status):
        if params.get("effect_if_present"):
            resolve_effect(state, params["effect_if_present"], ctx, rng)
    elif params.get("effect_if_absent"):
        resolve_effect(state, params["effect_if_absent"], ctx, rng)


def _evaluate_condition(state: GameState, condition: dict, ctx: EffectContext) -> bool:
    if "prior_choice" in condition:
        seat = _resolve_target(state, condition.get("target", "target"), ctx)
        within = int(condition.get("within_rounds", 3))
        return state.prior_choice_within(seat, condition["prior_choice"], within)
    if "has_status" in condition:
        seat = _resolve_target(state, condition.get("target", "target"), ctx)
        return state.has_status(seat, condition["has_status"])
    if "dice_failed" in condition:
        seat = _resolve_target(state, condition.get("target", "target"), ctx)
        card_id = condition.get("card_id", ctx.get("card_id", ""))
        within = int(condition.get("within_rounds", 2))
        return state.failed_dice_for_card(seat, card_id, within)
    if "gold_gt_king" in condition:
        seat = ctx["seat"]
        return state.person_at_seat(seat).gold > state.king_gold()
    return False


PRIMITIVE_REGISTRY: dict[str, EffectFn] = {
    "gold_gain": gold_gain,
    "gold_loss": gold_loss,
    "gold_transfer": gold_transfer,
    "steal_card": steal_card,
    "force_discard": force_discard,
    "draw_extra": draw_extra,
    "peek_card": peek_card,
    "reveal_hand": reveal_hand,
    "negate_effect": negate_effect,
    "redirect_effect": redirect_effect,
    "copy_last_effect": copy_last_effect,
    "swap_hands": swap_hands,
    "block_succession": block_succession,
    "protect_gold": protect_gold,
    "mark_status": mark_status,
    "alliance_bonus": alliance_bonus,
    "skip_next_play": skip_next_play,
    "gain_legitimacy": gain_legitimacy,
    "extra_play": extra_play,
    "conditional_swing": conditional_swing,
    "prompt_choice": prompt_choice,
    "roll_die": roll_die,
    "dice_swing": dice_swing,
    "conditional_on_choice": conditional_on_choice,
    "conditional_on_status": conditional_on_status,
    "on_whiff_penalty": on_whiff_penalty,
}

VALID_PRIMITIVES = frozenset(PRIMITIVE_REGISTRY.keys())
