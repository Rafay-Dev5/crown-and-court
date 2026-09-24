"""Plain-language descriptions of card JSON effects (mirrors viewer/src/cardText.ts)."""

from __future__ import annotations

from typing import Any


TARGET_LABELS = {
    "self": "you",
    "target": "your chosen opponent",
    "king": "the King",
}


def target_label(raw: Any) -> str:
    if not isinstance(raw, str):
        return "a player"
    return TARGET_LABELS.get(raw, raw)


def humanize_choice_id(choice_id: str) -> str:
    return " ".join(part.capitalize() for part in choice_id.replace("-", "_").split("_"))


def _gold_phrase(amount: Any, target: Any, verb: str) -> str:
    n = int(amount or 0)
    who = target_label(target)
    if verb == "gain":
        return f"{who} gain {n} gold"
    if verb == "lose":
        return f"{who} lose {n} gold"
    opponent = "an opponent" if who == "you" else who
    return f"{n} gold is taken from {opponent}"


def _shield_blurb(params: dict[str, Any]) -> tuple[str, str]:
    blocks = str(params.get("blocks") or "gold_theft")
    if blocks == "force_discard":
        return (
            "a shield against a forced discard",
            "While it is up, it stops a forced discard revealed after this card. "
            "It does not protect gold, and it does not undo a discard revealed before it. "
            "A hit keeps the shield. A miss removes it.",
        )
    return (
        "a shield against gold theft",
        "While it is up, it stops a gold theft revealed after this card, then it is used up. "
        "It does not undo a theft revealed before it. "
        "A hit keeps any unused shield. A miss removes it.",
    )


def _deferred_protection_lines(what: str, hit_when: str, outcome: str) -> list[str]:
    return [
        f"When this card is revealed, {what} goes up immediately and stays up through the rest of the reveals.",
        (
            "The guess is not scored then. It is checked after every card has been revealed, "
            f"before succession. It hits if {hit_when}."
        ),
        outcome,
    ]


def describe_trigger(trigger: dict[str, Any]) -> str:
    t = str(trigger.get("type", ""))
    if t == "attacked_this_phase":
        atk = trigger.get("attack_type")
        if atk:
            return f"you suffered a {str(atk).replace('_', ' ')} during this round's reveals"
        return "you were attacked in any way during this round's reveals"
    if t == "attacker_is":
        return "that attacker targeted you during this round's reveals"
    if t == "succession_imminent":
        return "a Noble has more gold than the King"
    if t == "always":
        return "always"
    return t.replace("_", " ")


def describe_condition(cond: dict[str, Any]) -> str:
    if cond.get("prior_choice"):
        choice = humanize_choice_id(str(cond["prior_choice"]))
        within = f" in the last {cond['within_rounds']} rounds" if cond.get("within_rounds") else ""
        return f'they previously chose “{choice}”{within}'
    if cond.get("target_prior_choice"):
        choice = humanize_choice_id(str(cond["target_prior_choice"]))
        within = f" in the last {cond['within_rounds']} rounds" if cond.get("within_rounds") else ""
        return f'your target previously chose “{choice}”{within}'
    if cond.get("dice_failed"):
        within = f" in the last {cond['within_rounds']} rounds" if cond.get("within_rounds") else ""
        return f"they failed a dice roll on a prior card{within}"
    if cond.get("has_status"):
        return f'they have the “{cond["has_status"]}” status'
    if cond.get("alliance_declared_with_target"):
        return "you have a declared alliance with your target"
    return "a special condition is met"


def _success_faces(sides: int, target_min: int) -> str:
    faces = [str(n) for n in range(int(target_min), int(sides) + 1)]
    if not faces:
        return "no number"
    if len(faces) == 1:
        return faces[0]
    if len(faces) == 2:
        return f"{faces[0]} or {faces[1]}"
    return ", ".join(faces[:-1]) + f", or {faces[-1]}"


def _describe_die(sides: int, target_min: int) -> str:
    return f"Roll a {sides}-sided die. Success on {_success_faces(sides, target_min)}."


def describe_effect_block(block: dict[str, Any] | None, depth: int = 0) -> list[str]:
    if not block or not block.get("primitive"):
        return []
    p = block.get("params") or {}
    lines: list[str] = []
    primitive = block["primitive"]

    if primitive == "gold_gain":
        lines.append(_gold_phrase(p.get("amount"), p.get("target", "self"), "gain") + ".")
    elif primitive == "gold_loss":
        if p.get("fraction_of_wealth") is not None:
            pct = int(round(float(p["fraction_of_wealth"]) * 100))
            lines.append(f"{target_label(p.get('target', 'self'))} lose {pct}% of your current gold.")
        else:
            lines.append(_gold_phrase(p.get("amount"), p.get("target", "self"), "lose") + ".")
    elif primitive == "gold_transfer":
        lines.append(
            f"{int(p.get('amount') or 0)} gold moves from "
            f"{target_label(p.get('from', 'target'))} to {target_label(p.get('to', 'self'))}."
        )
    elif primitive == "steal_card":
        lines.append(
            f"{target_label(p.get('to', 'self'))} steal {p.get('count', 1)} card(s) from "
            f"{target_label(p.get('from', 'target'))}."
        )
    elif primitive == "force_discard":
        lines.append(
            f"{target_label(p.get('target', 'target'))} chooses {p.get('count', 1)} card(s) to discard."
        )
    elif primitive == "draw_extra":
        lines.append(f"{target_label(p.get('target', 'self'))} draw {p.get('count', 1)} extra card(s).")
    elif primitive == "peek_card":
        who = target_label(p.get("target", "target"))
        lines.append(f"You peek at one card in {who}'s hand (only you see it).")
    elif primitive == "reveal_hand":
        lines.append(f"{target_label(p.get('target', 'target'))}'s hand is revealed to everyone.")
    elif primitive == "block_succession":
        if p.get("trigger"):
            lines.extend(_deferred_protection_lines(
                "the succession block",
                describe_trigger(p["trigger"]),
                (
                    "A hit keeps the block, so the succession check that follows can be stopped. "
                    "A miss removes the block before that check."
                ),
            ))
        else:
            lines.append("The next succession check is blocked.")
    elif primitive == "protect_gold":
        if p.get("trigger"):
            what, outcome = _shield_blurb(p)
            lines.extend(_deferred_protection_lines(what, describe_trigger(p["trigger"]), outcome))
        else:
            lines.append(
                f"Protect up to {p.get('amount', '?')} gold for {p.get('duration_rounds', 1)} round(s)."
            )
    elif primitive == "mark_status":
        lines.append(
            f"{target_label(p.get('target', 'self'))} receive the “{p.get('status_name')}” status "
            f"for {p.get('duration_rounds', 2)} round(s)."
        )
    elif primitive == "alliance_bonus":
        lines.append(
            f"You and the player you target each gain {p.get('amount', 50)} gold, "
            "but only if you are allied with them when this resolves. If you are not, the card does nothing."
        )
    elif primitive == "skip_next_play":
        lines.append(f"{target_label(p.get('target', 'target'))} play one fewer card next round.")
    elif primitive == "extra_play":
        lines.append(f"{target_label(p.get('target', 'self'))} may play an extra card next round.")
    elif primitive == "gain_legitimacy":
        lines.append(f"{target_label(p.get('target', 'self'))} gain {p.get('amount', 1)} legitimacy.")
    elif primitive == "swap_hands":
        lines.append("Two players swap hands.")
    elif primitive == "dice_swing":
        choice_seat = p.get("choice_seat", "self")
        chooser = "Your chosen opponent chooses" if choice_seat == "target" else "Choose"
        choices = p.get("choices") or []
        if choices:
            lines.append(f"{chooser} one path:")
            for c in choices:
                lines.append(f"  • {c.get('label', humanize_choice_id(str(c.get('id', ''))))}")
        branches = p.get("branches") or {}
        for choice_id, branch in branches.items():
            label = next(
                (c.get("label") for c in choices if c.get("id") == choice_id),
                humanize_choice_id(str(choice_id)),
            )
            die = branch.get("die")
            if die:
                sides = int(die.get("sides", 6))
                need = int(die.get("target_min", 4))
                lines.append(f'If “{label}” is chosen: {_describe_die(sides, need)}')
            else:
                lines.append(f'If “{label}” is chosen:')
            if branch.get("on_success"):
                success = " ".join(describe_effect_block(branch["on_success"]))
                lines.append(f"  Success: {success}" if die else f"  {success}")
            if branch.get("on_failure"):
                lines.append(f"  Failure: {' '.join(describe_effect_block(branch['on_failure']))}")
            if branch.get("on_failure_status"):
                st = branch["on_failure_status"]
                lines.append(
                    f"  On failure they also get “{st.get('status_name')}” for "
                    f"{st.get('duration_rounds', 2)} round(s)."
                )
    elif primitive == "conditional_swing":
        cond = p.get("condition") or {}
        lines.append(f"If {describe_condition(cond)}:")
        if p.get("effect_if_true"):
            lines.append(f"  Then: {' '.join(describe_effect_block(p['effect_if_true']))}")
        if p.get("effect_if_false"):
            lines.append(f"  Otherwise: {' '.join(describe_effect_block(p['effect_if_false']))}")
    elif primitive == "prompt_choice":
        options = p.get("options") or []
        lines.append("Choose one:")
        for o in options:
            lines.append(f"  • {o.get('label', humanize_choice_id(str(o.get('id', ''))))}")
    elif primitive == "roll_die":
        sides = int(p.get("sides") or 6)
        need = int(p.get("target_min") or 4)
        lines.append(_describe_die(sides, need))
    elif primitive == "conditional_on_status":
        who = target_label(p.get("target", "target"))
        lines.append(f"If {who} has the “{p.get('status_name')}” status:")
        if p.get("effect_if_present"):
            lines.append(f"  Then: {' '.join(describe_effect_block(p['effect_if_present']))}")
        if p.get("effect_if_absent"):
            lines.append(f"  Otherwise: {' '.join(describe_effect_block(p['effect_if_absent']))}")
    elif primitive == "conditional_on_choice":
        who = target_label(p.get("target", "target"))
        choice = humanize_choice_id(str(p.get("choice_id") or "a path"))
        within = f" in the last {p['within_rounds']} rounds" if p.get("within_rounds") else ""
        lines.append(f"If {who} previously chose “{choice}”{within}:")
        if p.get("effect_if_match"):
            lines.append(f"  Then: {' '.join(describe_effect_block(p['effect_if_match']))}")
        if p.get("effect_if_no_match"):
            lines.append(f"  Otherwise: {' '.join(describe_effect_block(p['effect_if_no_match']))}")
    else:
        lines.append(f"{str(primitive).replace('_', ' ')} (see technical details).")

    if block.get("secondary_effect"):
        lines.append("Then: " + " ".join(describe_effect_block(block["secondary_effect"], depth + 1)))
    return lines


def describe_requires_state(req: dict[str, Any] | None) -> list[str]:
    if not req:
        return []
    lines = ["Can only be played if:"]
    if req.get("alliance_declared_with_target"):
        lines.append("  • You have a declared alliance with your target.")
    if req.get("prior_choice"):
        lines.append(f'  • You previously chose “{humanize_choice_id(str(req["prior_choice"]))}”.')
    if req.get("target_prior_choice"):
        within = f" (within {req['within_rounds']} rounds)" if req.get("within_rounds") else ""
        lines.append(
            f'  • Your target previously chose “{humanize_choice_id(str(req["target_prior_choice"]))}”{within}.'
        )
    return lines


def describe_whiff_penalty(block: dict[str, Any] | None) -> list[str]:
    if not block:
        return []
    return [
        "If the guess misses:",
        *[f"  {line}" for line in describe_effect_block(block)],
    ]


def describe_timing(timing: str) -> str:
    return {
        "on_reveal": "Resolves when revealed in play order.",
        "reactive": (
            "Played face-down. It arms when revealed and stays up. "
            "The guess is scored after every card has been revealed, before succession."
        ),
        "end_of_round": "Resolves at the end of the round.",
        "negotiation_only": "Only usable during the negotiation phase.",
    }.get(timing, timing)


def describe_card_summary(card: dict[str, Any]) -> str:
    lines = describe_effect_block(card.get("effect"))
    if not lines:
        return "See card details."
    first = lines[0]
    return first if len(first) <= 140 else first[:137] + "…"


def _capitalize_sentence(line: str) -> str:
    if not line or line.startswith("  "):
        return line
    return line[0].upper() + line[1:]


def describe_card_full_lines(card: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    timing = card.get("timing") or "on_reveal"
    lines.append(describe_timing(timing))

    req = describe_requires_state(card.get("requires_state"))
    if len(req) > 1:
        lines.extend(req)

    effect_lines = describe_effect_block(card.get("effect"))
    if effect_lines:
        lines.extend(_capitalize_sentence(line) for line in effect_lines)

    whiff = describe_whiff_penalty(card.get("on_whiff_penalty"))
    if whiff:
        lines.extend(whiff)

    lines.extend(_card_warnings(card))

    return lines


def _card_warnings(card: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    effect = card.get("effect") or {}
    requires = card.get("requires_state") or {}
    needs_alliance = (
        card.get("category") == "alliance"
        or effect.get("primitive") == "alliance_bonus"
        or requires.get("alliance_declared_with_target")
    )
    if card.get("category") == "betrayal":
        secondary = effect.get("secondary_effect")
        extra = " ".join(describe_effect_block(secondary)) if secondary else ""
        if extra:
            warnings.append(
                "Warning: only playable while you are allied, and only against that ally. "
                f"Betrayal cost (paid even if a shield stops the theft): {extra}"
            )
        else:
            warnings.append(
                "Warning: only playable while you are allied, and only against that ally."
            )
    if needs_alliance:
        warnings.append(
            "Warning: this needs an alliance with your target. Otherwise it does nothing."
        )
    return warnings
