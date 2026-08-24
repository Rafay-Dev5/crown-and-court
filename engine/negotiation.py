"""Negotiation: trades, alliances, and related helpers.

Allowed trade kinds (no gold↔gold):
  - gold_for_cards: gold one way, cards the other
  - cards_for_gold: cards one way, gold the other (same exchange, opposite initiator)
  - cards_for_cards: cards both ways

Each card is worth CARD_GOLD_VALUE gold for imbalance / Oathbreaker checks.
"""

from __future__ import annotations

from typing import Any, Callable

from engine.rng import GameRNG
from engine.state import Alliance, ConditionalPromise, GameState, Phase

CARD_GOLD_VALUE = 40
MAX_CARDS_FOR_CARDS_PER_PHASE = 5
OATHBREAKER_DURATION = 2


def _trade_card_summary(card: dict[str, Any]) -> dict[str, Any]:
    """Public card face for trade previews (shown before accept/confirm)."""
    return {
        "id": card.get("id"),
        "name": card.get("name"),
        "category": card.get("category"),
        "rarity": card.get("rarity"),
        "effect": card.get("effect"),
        "flavor_text": card.get("flavor_text"),
    }


def _summaries_for_ids(state: GameState, seat: int, card_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {c.get("id"): c for c in state.seats[seat].hand}
    out: list[dict[str, Any]] = []
    for cid in card_ids:
        card = by_id.get(cid)
        if card is not None:
            out.append(_trade_card_summary(card))
    return out


def _next_proposal_id(state: GameState) -> str:
    state.proposal_counter += 1
    return f"p{state.proposal_counter}"


def _gold_amount(payload: dict[str, Any] | None) -> int:
    if not payload:
        return 0
    return max(0, int(payload.get("gold", 0) or 0))


def _card_ids(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    raw = payload.get("cards") or []
    return [str(c) for c in raw if c]


def _card_count_request(payload: dict[str, Any] | None) -> int:
    """How many cards the counterparty must supply (by count, not by id)."""
    if not payload:
        return 0
    ids = _card_ids(payload)
    if ids:
        return len(ids)
    return max(0, int(payload.get("card_count", 0) or 0))


def classify_trade(offer: dict[str, Any], request: dict[str, Any]) -> str:
    """Return trade kind or raise ValueError if illegal / empty."""
    og = _gold_amount(offer)
    rg = _gold_amount(request)
    oc = len(_card_ids(offer))
    rc = _card_count_request(request)

    if og > 0 and rg > 0:
        raise ValueError("Gold-for-gold trades are not allowed")
    if og > 0 and oc > 0:
        raise ValueError("A side cannot offer both gold and cards")
    if rg > 0 and rc > 0:
        raise ValueError("A side cannot request both gold and cards")
    if og == 0 and rg == 0 and oc == 0 and rc == 0:
        raise ValueError("Empty trade")

    if og > 0 and rc > 0 and rg == 0 and oc == 0:
        return "gold_for_cards"
    if oc > 0 and rg > 0 and og == 0 and rc == 0:
        return "cards_for_gold"
    if oc > 0 and rc > 0 and og == 0 and rg == 0:
        return "cards_for_cards"
    raise ValueError(
        "Trades must be gold-for-cards, cards-for-gold, or cards-for-cards"
    )


def propose_trade(
    state: GameState,
    proposer: int,
    target: int,
    offer: dict[str, Any],
    request: dict[str, Any],
) -> str:
    if proposer == target:
        raise ValueError("Cannot propose a trade with yourself")
    if not (0 <= target < state.num_players):
        raise ValueError("Invalid trade target")

    offer = {
        "gold": _gold_amount(offer),
        "cards": _card_ids(offer),
        "card_count": 0,
    }
    request = {
        "gold": _gold_amount(request),
        "cards": _card_ids(request),
        "card_count": max(0, int((request or {}).get("card_count", 0) or 0)),
    }
    # If explicit card ids were put on the request, treat them as a count request
    # that the accepter must still fulfill from their hand at accept time.
    if request["cards"] and request["card_count"] <= 0:
        request["card_count"] = len(request["cards"])
        request["cards"] = []

    kind = classify_trade(offer, request)

    # Proposer must currently hold offered cards.
    offer_details: list[dict[str, Any]] = []
    if offer["cards"]:
        hand_ids = [c.get("id") for c in state.seats[proposer].hand]
        for cid in offer["cards"]:
            if cid not in hand_ids:
                raise ValueError(f"You do not hold card {cid}")
            hand_ids.remove(cid)
        offer_details = _summaries_for_ids(state, proposer, offer["cards"])
        if len(offer_details) != len(offer["cards"]):
            raise ValueError("Could not resolve offered cards")

    if kind == "cards_for_cards":
        sent = state.negotiation_cards_sent.get(proposer, 0)
        if sent + len(offer["cards"]) > MAX_CARDS_FOR_CARDS_PER_PHASE:
            raise ValueError(
                f"Card-for-card gifts are capped at {MAX_CARDS_FOR_CARDS_PER_PHASE} "
                "cards per negotiation phase"
            )

    offer["card_details"] = offer_details

    pid = _next_proposal_id(state)
    proposal = {
        "id": pid,
        "type": "trade",
        "kind": kind,
        "proposer": proposer,
        "target": target,
        "offer": offer,
        "request": request,
        "status": "pending",
    }
    state.pending_proposals.append(proposal)
    state.negotiation_history.append(proposal)
    state.log_event(
        "propose_trade",
        proposal_id=pid,
        proposer=proposer,
        target=target,
        kind=kind,
        offer_gold=offer["gold"],
        request_gold=request["gold"],
        offer_cards=len(offer["cards"]),
        request_cards=request["card_count"],
    )
    return pid


def propose_alliance(
    state: GameState,
    proposer: int,
    targets: list[int],
    terms: str = "",
) -> str:
    cleaned = [int(t) for t in targets if int(t) != proposer and 0 <= int(t) < state.num_players]
    if not cleaned:
        raise ValueError("Alliance requires at least one other player")
    pid = _next_proposal_id(state)
    proposal = {
        "id": pid,
        "type": "alliance",
        "proposer": proposer,
        "targets": cleaned,
        "terms": terms,
        "status": "pending",
    }
    state.pending_proposals.append(proposal)
    state.negotiation_history.append(proposal)
    state.log_event("propose_alliance", proposal_id=pid, proposer=proposer, targets=cleaned)
    return pid


def propose_conditional(
    state: GameState,
    proposer: int,
    target: int,
    offer: dict[str, Any],
    condition: dict[str, Any],
) -> str:
    """Non-binding promise referencing future game state — anyone can promise anything, anyone can break it."""
    pid = _next_proposal_id(state)
    promise = ConditionalPromise(
        id=pid,
        proposer=proposer,
        target=target,
        offer=offer,
        condition=condition,
        declared_round=state.current_round,
    )
    state.conditional_promises.append(promise)
    proposal = {
        "id": pid,
        "type": "conditional",
        "proposer": proposer,
        "target": target,
        "offer": offer,
        "condition": condition,
        "status": "pending",
    }
    state.pending_proposals.append(proposal)
    state.negotiation_history.append(proposal)
    state.log_event(
        "propose_conditional",
        proposal_id=pid,
        proposer=proposer,
        target=target,
        condition=condition,
    )
    return pid


def accept_proposal(
    state: GameState,
    accepter: int,
    proposal_id: str,
    fulfillment_cards: list[str] | None = None,
) -> bool:
    proposal = next((p for p in state.pending_proposals if p["id"] == proposal_id), None)
    if not proposal or proposal["status"] != "pending":
        return False

    if proposal["type"] == "trade":
        if accepter != proposal["target"]:
            return False
        request = dict(proposal["request"] or {})
        needed = _card_count_request(request)
        if needed > 0:
            cards = [str(c) for c in (fulfillment_cards or [])]
            if len(cards) != needed:
                state.log_event(
                    "trade_blocked",
                    proposer=proposal["proposer"],
                    target=accepter,
                    reason="fulfillment_cards_mismatch",
                    needed=needed,
                    provided=len(cards),
                )
                return False
            hand_ids = [c.get("id") for c in state.seats[accepter].hand]
            for cid in cards:
                if cid not in hand_ids:
                    state.log_event(
                        "trade_blocked",
                        proposer=proposal["proposer"],
                        target=accepter,
                        reason="missing_fulfillment_card",
                        card_id=cid,
                    )
                    return False
                hand_ids.remove(cid)
            request["cards"] = cards
            request["card_count"] = 0
            request["card_details"] = _summaries_for_ids(state, accepter, cards)
            # Interactive table: card receiver (proposer) must see cards and confirm.
            if state.config.get("pause_between_reveals"):
                proposal["request"] = request
                proposal["status"] = "pending_confirm"
                state.log_event(
                    "trade_cards_revealed",
                    proposal_id=proposal_id,
                    proposer=proposal["proposer"],
                    target=accepter,
                    cards=request["card_details"],
                )
                return True
        if not _execute_trade(
            state, proposal["proposer"], proposal["target"], proposal["offer"], request
        ):
            return False
    elif proposal["type"] == "conditional":
        if accepter != proposal["target"]:
            return False
        promise = next((p for p in state.conditional_promises if p.id == proposal_id), None)
        if promise:
            promise.status = "accepted"
        state.log_event("conditional_accepted", proposal_id=proposal_id, note="non_binding")
    elif proposal["type"] == "alliance":
        targets = proposal.get("targets") or []
        if accepter not in targets:
            return False
        members = frozenset([proposal["proposer"], *targets])
        state.alliances.append(
            Alliance(members=members, declared_round=state.current_round, terms=proposal.get("terms", ""))
        )
        state.log_event("alliance_formed", members=list(members))
    else:
        return False

    proposal["status"] = "accepted"
    state.log_event("proposal_accepted", proposal_id=proposal_id, accepter=accepter)
    return True


def confirm_proposal(state: GameState, confirmer: int, proposal_id: str) -> bool:
    """Proposer confirms a trade after seeing the counterparty's chosen cards."""
    proposal = next((p for p in state.pending_proposals if p["id"] == proposal_id), None)
    if not proposal or proposal["status"] != "pending_confirm":
        return False
    if proposal["type"] != "trade" or confirmer != proposal["proposer"]:
        return False
    offer = proposal["offer"]
    request = proposal["request"]
    # Re-validate offered cards still in proposer's hand.
    for cid in _card_ids(offer):
        if not any(c.get("id") == cid for c in state.seats[confirmer].hand):
            state.log_event(
                "trade_blocked",
                proposer=confirmer,
                target=proposal["target"],
                reason="offer_cards_no_longer_held",
            )
            proposal["status"] = "rejected"
            return False
    # Re-validate fulfillment cards still in target's hand.
    for cid in _card_ids(request):
        if not any(c.get("id") == cid for c in state.seats[proposal["target"]].hand):
            state.log_event(
                "trade_blocked",
                proposer=confirmer,
                target=proposal["target"],
                reason="fulfillment_cards_no_longer_held",
            )
            proposal["status"] = "rejected"
            return False
    if not _execute_trade(
        state, proposal["proposer"], proposal["target"], offer, request
    ):
        return False
    proposal["status"] = "accepted"
    state.log_event("proposal_accepted", proposal_id=proposal_id, accepter=confirmer, confirmed=True)
    return True


def reject_proposal(state: GameState, rejecter: int, proposal_id: str) -> bool:
    proposal = next((p for p in state.pending_proposals if p["id"] == proposal_id), None)
    if not proposal or proposal["status"] not in ("pending", "pending_confirm"):
        return False
    is_target = proposal.get("target") == rejecter
    is_alliance_target = rejecter in (proposal.get("targets") or [])
    is_proposer_confirm = (
        proposal["status"] == "pending_confirm" and proposal.get("proposer") == rejecter
    )
    if not is_target and not is_alliance_target and not is_proposer_confirm:
        return False
    proposal["status"] = "rejected"
    state.log_event("proposal_rejected", proposal_id=proposal_id, rejecter=rejecter)
    return True


def threaten(state: GameState, actor: int, target: int, terms: str) -> None:
    state.log_event("threaten", actor=actor, target=target, terms=terms)
    state.negotiation_history.append(
        {"type": "threaten", "actor": actor, "target": target, "terms": terms}
    )


def pass_action(state: GameState, seat: int) -> None:
    state.log_event("negotiation_pass", seat=seat)


def _maybe_brand_oathbreaker(
    state: GameState,
    seat: int,
    *,
    gold_given: int,
    cards_given: int,
    gold_received: int,
    cards_received: int,
    kind: str,
) -> None:
    brand = False
    reason = ""
    if kind in ("gold_for_cards", "cards_for_gold"):
        # Convert cards at CARD_GOLD_VALUE. Brand whoever received the higher
        # value if the lower side got ≤ half of that higher value.
        value_received = gold_received + cards_received * CARD_GOLD_VALUE
        value_counterparty = gold_given + cards_given * CARD_GOLD_VALUE
        if value_received > value_counterparty and value_counterparty <= 0.5 * value_received:
            brand = True
            reason = "gold_card_value_imbalance"
    elif kind == "cards_for_cards":
        if cards_received > 3 * max(cards_given, 0):
            brand = True
            reason = "cards_for_cards_imbalance"

    if brand:
        state.apply_status(seat, "oathbreaker", OATHBREAKER_DURATION)
        state.log_event(
            "mark_status",
            seat=seat,
            status="oathbreaker",
            duration=OATHBREAKER_DURATION,
            reason=reason,
            gold_given=gold_given,
            cards_given=cards_given,
            gold_received=gold_received,
            cards_received=cards_received,
        )


def _execute_trade(
    state: GameState,
    proposer: int,
    target: int,
    offer: dict[str, Any],
    request: dict[str, Any],
) -> bool:
    """Execute an allowed trade. Returns False if blocked."""
    try:
        kind = classify_trade(offer, request)
    except ValueError as exc:
        state.log_event(
            "trade_blocked",
            proposer=proposer,
            target=target,
            reason=str(exc),
        )
        return False

    max_trades = int(state.config.get("max_negotiation_trades_per_phase", 0))
    if max_trades > 0:
        for seat in (proposer, target):
            if state.negotiation_trades_executed.get(seat, 0) >= max_trades:
                state.log_event(
                    "trade_blocked",
                    proposer=proposer,
                    target=target,
                    reason="max_negotiation_trades_per_phase",
                    seat=seat,
                )
                return False

    if kind == "cards_for_cards":
        for seat, cards in (
            (proposer, _card_ids(offer)),
            (target, _card_ids(request)),
        ):
            sent = state.negotiation_cards_sent.get(seat, 0)
            if sent + len(cards) > MAX_CARDS_FOR_CARDS_PER_PHASE:
                state.log_event(
                    "trade_blocked",
                    proposer=proposer,
                    target=target,
                    reason="max_cards_for_cards_per_phase",
                    seat=seat,
                    attempted=len(cards),
                    already_sent=sent,
                )
                return False

    trade_cap = int(state.config.get("max_negotiation_gift_per_trade", 0))
    trade_remaining: dict[int, int] = {}
    if trade_cap > 0:
        trade_remaining[proposer] = trade_cap
        trade_remaining[target] = trade_cap

    out_p = _apply_trade_payload(state, proposer, offer, target, trade_remaining, kind=kind)
    out_t = _apply_trade_payload(state, target, request, proposer, trade_remaining, kind=kind)

    _maybe_brand_oathbreaker(
        state,
        proposer,
        gold_given=out_p["gold"],
        cards_given=out_p["cards"],
        gold_received=out_t["gold"],
        cards_received=out_t["cards"],
        kind=kind,
    )
    _maybe_brand_oathbreaker(
        state,
        target,
        gold_given=out_t["gold"],
        cards_given=out_t["cards"],
        gold_received=out_p["gold"],
        cards_received=out_p["cards"],
        kind=kind,
    )

    for seat in (proposer, target):
        state.negotiation_trades_executed[seat] = state.negotiation_trades_executed.get(seat, 0) + 1
    state.log_event(
        "trade_executed",
        proposer=proposer,
        target=target,
        kind=kind,
        offer_gold=out_p["gold"],
        offer_cards=out_p["cards"],
        request_gold=out_t["gold"],
        request_cards=out_t["cards"],
    )
    return True


def _apply_trade_payload(
    state: GameState,
    seat: int,
    payload: dict[str, Any],
    counterparty: int,
    trade_remaining: dict[int, int] | None = None,
    *,
    kind: str,
) -> dict[str, int]:
    """Move gold/cards from seat to counterparty. Oathbreaker cannot receive either."""
    person = state.person_at_seat(seat)
    other = state.person_at_seat(counterparty)
    result = {"gold": 0, "cards": 0}

    gold = _gold_amount(payload)
    max_gift = int(state.config.get("max_negotiation_gift", 0))
    if max_gift > 0:
        gold = min(gold, max_gift)
    if trade_remaining is not None and seat in trade_remaining:
        gold = min(gold, trade_remaining[seat])
    phase_cap = int(state.config.get("max_negotiation_gift_per_phase", 0))
    if phase_cap > 0:
        sent = state.negotiation_gift_sent.get(seat, 0)
        gold = min(gold, max(0, phase_cap - sent))

    if gold > 0 and state.has_status(counterparty, "oathbreaker"):
        state.log_event(
            "gift_blocked_by_status",
            from_seat=seat,
            to_seat=counterparty,
            status="oathbreaker",
            attempted_amount=gold,
            gift_type="gold",
        )
        gold = 0

    if gold > 0:
        transfer = min(gold, person.gold)
        person.gold -= transfer
        person.earned_gold = max(0, person.earned_gold - transfer)
        other.gold += transfer
        other.earned_gold += transfer
        state.negotiation_gift_sent[seat] = state.negotiation_gift_sent.get(seat, 0) + transfer
        if trade_remaining is not None and seat in trade_remaining:
            trade_remaining[seat] = max(0, trade_remaining[seat] - transfer)
        state.log_event(
            "gold_gifted",
            from_seat=seat,
            to_seat=counterparty,
            from_person=person.person_id,
            to_person=other.person_id,
            amount=transfer,
        )
        result["gold"] = transfer

    cards = _card_ids(payload)
    if cards and state.has_status(counterparty, "oathbreaker"):
        state.log_event(
            "gift_blocked_by_status",
            from_seat=seat,
            to_seat=counterparty,
            status="oathbreaker",
            attempted_cards=len(cards),
            gift_type="cards",
        )
        cards = []

    moved = 0
    for card_id in cards:
        for idx, card in enumerate(state.seats[seat].hand):
            if card.get("id") == card_id:
                state.seats[seat].hand.pop(idx)
                state.seats[counterparty].hand.append(card)
                moved += 1
                state.log_event(
                    "card_gifted",
                    from_seat=seat,
                    to_seat=counterparty,
                    card_id=card_id,
                    card_name=card.get("name"),
                )
                break
    result["cards"] = moved

    if kind == "cards_for_cards" and moved > 0:
        state.negotiation_cards_sent[seat] = state.negotiation_cards_sent.get(seat, 0) + moved

    return result


def run_negotiation_phase(
    state: GameState,
    rng: GameRNG,
    policy: Callable[[GameState, int, GameRNG], None] | None = None,
) -> None:
    state.phase = Phase.NEGOTIATION
    state.pending_proposals = []
    state.negotiation_gift_sent = {}
    state.negotiation_cards_sent = {}
    state.negotiation_trades_executed = {}
    ticks = int(state.config.get("negotiation_ticks", 4))
    order = state.seat_order_from_king()

    for tick in range(ticks):
        for seat in order:
            if policy:
                policy(state, seat, rng)
            else:
                pass_action(state, seat)

    state.log_event("negotiation_complete", ticks=ticks)


def random_negotiation_policy(state: GameState, seat: int, rng: GameRNG) -> None:
    others = [s for s in range(state.num_players) if s != seat]
    if not others:
        pass_action(state, seat)
        return
    target = rng.choice(others)
    action = rng.randint(0, 3)
    hand = state.seats[seat].hand
    if action == 0 and hand and not state.has_status(target, "oathbreaker"):
        # Cards for gold: sell one card for a modest price (often brands the buyer).
        card = hand[0]
        try:
            propose_trade(
                state,
                seat,
                target,
                {"gold": 0, "cards": [card["id"]]},
                {"gold": 30, "card_count": 0},
            )
        except ValueError:
            pass_action(state, seat)
    elif action == 1 and len(others) >= 1:
        propose_alliance(state, seat, [target], terms="mutual support")
    elif action == 2 and state.pending_proposals:
        pending = [
            p
            for p in state.pending_proposals
            if p["status"] == "pending" and p.get("target") == seat
        ]
        if pending and rng.random() > 0.5:
            prop = pending[0]
            needed = _card_count_request(prop.get("request"))
            fulfillment: list[str] = []
            if needed > 0:
                fulfillment = [c["id"] for c in state.seats[seat].hand[:needed]]
                if len(fulfillment) < needed:
                    pass_action(state, seat)
                    return
            accept_proposal(state, seat, prop["id"], fulfillment_cards=fulfillment or None)
        else:
            pass_action(state, seat)
    else:
        pass_action(state, seat)
