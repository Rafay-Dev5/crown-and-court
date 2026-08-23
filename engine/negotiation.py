from __future__ import annotations

from typing import Any, Callable

from engine.rng import GameRNG
from engine.state import Alliance, ConditionalPromise, GameState, Phase, StatusTag


def _next_proposal_id(state: GameState) -> str:
    state.proposal_counter += 1
    return f"p{state.proposal_counter}"


def propose_trade(
    state: GameState,
    proposer: int,
    target: int,
    offer: dict[str, Any],
    request: dict[str, Any],
) -> str:
    pid = _next_proposal_id(state)
    proposal = {
        "id": pid,
        "type": "trade",
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
        offer_gold=int(offer.get("gold", 0) or 0),
        request_gold=int(request.get("gold", 0) or 0),
    )
    return pid


def propose_alliance(
    state: GameState,
    proposer: int,
    targets: list[int],
    terms: str = "",
) -> str:
    pid = _next_proposal_id(state)
    proposal = {
        "id": pid,
        "type": "alliance",
        "proposer": proposer,
        "targets": targets,
        "terms": terms,
        "status": "pending",
    }
    state.pending_proposals.append(proposal)
    state.negotiation_history.append(proposal)
    state.log_event("propose_alliance", proposal_id=pid, proposer=proposer, targets=targets)
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


def accept_proposal(state: GameState, accepter: int, proposal_id: str) -> bool:
    proposal = next((p for p in state.pending_proposals if p["id"] == proposal_id), None)
    if not proposal or proposal["status"] != "pending":
        return False

    if proposal["type"] == "trade":
        if accepter != proposal["target"]:
            return False
        _execute_trade(state, proposal["proposer"], proposal["target"], proposal["offer"], proposal["request"])
    elif proposal["type"] == "conditional":
        if accepter != proposal["target"]:
            return False
        promise = next((p for p in state.conditional_promises if p.id == proposal_id), None)
        if promise:
            promise.status = "accepted"
        state.log_event("conditional_accepted", proposal_id=proposal_id, note="non_binding")
    elif proposal["type"] == "alliance":
        members = frozenset([proposal["proposer"], *proposal["targets"]])
        if accepter not in members:
            return False
        state.alliances.append(
            Alliance(members=members, declared_round=state.current_round, terms=proposal.get("terms", ""))
        )
        state.log_event("alliance_formed", members=list(members))

    proposal["status"] = "accepted"
    state.log_event("proposal_accepted", proposal_id=proposal_id, accepter=accepter)
    return True


def reject_proposal(state: GameState, rejecter: int, proposal_id: str) -> bool:
    proposal = next((p for p in state.pending_proposals if p["id"] == proposal_id), None)
    if not proposal or proposal["status"] != "pending":
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


def _execute_trade(
    state: GameState,
    proposer: int,
    target: int,
    offer: dict[str, Any],
    request: dict[str, Any],
) -> None:
    """Execute gold/card trade. Gifted gold tracked separately."""
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
                return

    trade_cap = int(state.config.get("max_negotiation_gift_per_trade", 0))
    trade_remaining: dict[int, int] = {}
    if trade_cap > 0:
        trade_remaining[proposer] = trade_cap
        trade_remaining[target] = trade_cap

    _apply_trade_payload(state, proposer, offer, target, trade_remaining)
    _apply_trade_payload(state, target, request, proposer, trade_remaining)
    for seat in (proposer, target):
        state.negotiation_trades_executed[seat] = state.negotiation_trades_executed.get(seat, 0) + 1
    state.log_event("trade_executed", proposer=proposer, target=target)


def _apply_trade_payload(
    state: GameState,
    seat: int,
    payload: dict[str, Any],
    counterparty: int,
    trade_remaining: dict[int, int] | None = None,
) -> None:
    person = state.person_at_seat(seat)
    other = state.person_at_seat(counterparty)

    gold = int(payload.get("gold", 0))
    max_gift = int(state.config.get("max_negotiation_gift", 0))
    if max_gift > 0:
        gold = min(gold, max_gift)
    if trade_remaining is not None and seat in trade_remaining:
        gold = min(gold, trade_remaining[seat])
    phase_cap = int(state.config.get("max_negotiation_gift_per_phase", 0))
    if phase_cap > 0:
        sent = state.negotiation_gift_sent.get(seat, 0)
        gold = min(gold, max(0, phase_cap - sent))
    if gold > 0:
        if state.has_status(counterparty, "oathbreaker"):
            state.log_event(
                "gift_blocked_by_status",
                from_seat=seat,
                to_seat=counterparty,
                status="oathbreaker",
                attempted_amount=gold,
            )
            gold = 0
    if gold > 0:
        transfer = min(gold, person.gold)
        person.gold -= transfer
        earned_part = min(transfer, person.earned_gold)
        person.earned_gold -= earned_part
        other.gold += transfer
        other.gifted_gold += transfer
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
        state.seats[counterparty].statuses.append(
            StatusTag(name="oathbreaker", expires_after_round=state.current_round + 2)
        )
        state.log_event(
            "mark_status",
            seat=counterparty,
            status="oathbreaker",
            duration=2,
            reason="negotiation_gift_received",
        )

    cards = payload.get("cards", [])
    for card_id in cards:
        for idx, card in enumerate(state.seats[seat].hand):
            if card.get("id") == card_id:
                state.seats[seat].hand.pop(idx)
                state.seats[counterparty].hand.append(card)
                break


def run_negotiation_phase(
    state: GameState,
    rng: GameRNG,
    policy: Callable[[GameState, int, GameRNG], None] | None = None,
) -> None:
    state.phase = Phase.NEGOTIATION
    state.pending_proposals = []
    state.negotiation_gift_sent = {}
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
    if action == 0:
        propose_trade(state, seat, target, {"gold": 50}, {"gold": 0})
    elif action == 1 and len(others) >= 1:
        propose_alliance(state, seat, [target], terms="mutual support")
    elif action == 2 and state.pending_proposals:
        pending = [p for p in state.pending_proposals if p["status"] == "pending" and p.get("target") == seat]
        if pending and rng.random() > 0.5:
            accept_proposal(state, seat, pending[0]["id"])
        else:
            pass_action(state, seat)
    else:
        pass_action(state, seat)
