"""Interactive discard choice and private peek visibility."""

from __future__ import annotations

from engine.cards import load_all_cards
from engine.decisions import DecisionType
from web.server.game_session import GameSession, HumanAction


def _pass_negotiation(session: GameSession) -> None:
    while session.current_decision() and session.current_decision().dtype == DecisionType.NEGOTIATION:
        session.apply_action(HumanAction(action_type="pass"))


def _advance_until(
    session: GameSession,
    predicate,
    *,
    prefer_play_first: int | None = None,
    prefer_card_id: str | None = None,
    limit: int = 120,
) -> None:
    for _ in range(limit):
        dec = session.current_decision()
        assert dec is not None
        if predicate(dec):
            return
        if dec.dtype == DecisionType.PLAY:
            n = int(dec.context.get("n_play", 2))
            idxs = list(range(n))
            if prefer_play_first is not None and dec.seat == prefer_play_first and prefer_card_id:
                hand = session.state.seats[dec.seat].hand
                for i, card in enumerate(hand):
                    if card.get("id") == prefer_card_id:
                        idxs = [i] + [j for j in range(len(hand)) if j != i][: n - 1]
                        break
            session.apply_action(
                HumanAction(action_type="play", payload={"card_indices": idxs[:n]})
            )
        elif dec.dtype == DecisionType.TARGET:
            legal = list(dec.context.get("legal_targets") or [0])
            session.apply_action(
                HumanAction(action_type="choose_target", payload={"target_seat": legal[0]})
            )
        elif dec.dtype == DecisionType.CHOICE:
            session.apply_action(HumanAction(action_type="choice", payload={"choice_index": 0}))
        elif dec.dtype == DecisionType.DISCARD:
            count = int(dec.context.get("count", 1))
            session.apply_action(
                HumanAction(action_type="discard", payload={"card_indices": list(range(count))})
            )
        elif dec.dtype == DecisionType.REVEAL:
            session.apply_action(HumanAction(action_type="continue_reveal"))
        elif dec.dtype == DecisionType.NEGOTIATION:
            session.apply_action(HumanAction(action_type="pass"))
        else:
            raise AssertionError(f"unexpected dtype {dec.dtype}")
    raise AssertionError("predicate never matched")


def test_victim_chooses_which_card_to_discard():
    session = GameSession(
        ["a", "b", "c", "d"],
        ["King", "Noble1", "Noble2", "Noble3"],
        starting_king_seat=0,
        seed=11,
    )
    _pass_negotiation(session)

    cards = {c["id"]: c for c in load_all_cards()}
    sabotage = cards["noble_sabotage_001"]
    attacker = 1
    victim = 2
    session.state.seats[attacker].hand = [sabotage, *session.state.seats[attacker].hand]

    _advance_until(
        session,
        lambda d: d.dtype == DecisionType.TARGET
        and d.context.get("card", {}).get("id") == "noble_sabotage_001",
        prefer_play_first=attacker,
        prefer_card_id="noble_sabotage_001",
    )

    marker_a = {**cards["noble_development_fund_001"], "id": "marker_keep", "name": "Keep Me"}
    marker_b = {**cards["noble_development_fund_001"], "id": "marker_toss", "name": "Toss Me"}
    # Inject after plays so the victim still holds both when choosing.
    session.state.seats[victim].hand = [marker_a, marker_b, *session.state.seats[victim].hand]

    session.apply_action(
        HumanAction(action_type="choose_target", payload={"target_seat": victim})
    )

    dec = session.current_decision()
    assert dec is not None and dec.dtype == DecisionType.DISCARD
    assert dec.seat == victim
    assert int(dec.context.get("count", 0)) == 1

    private = session.build_private_state("c")  # seat 2
    assert private.discard_choice is not None
    assert private.discard_choice["count"] == 1
    assert private.discard_choice["hand"][0]["id"] == "marker_keep"
    assert private.discard_choice["hand"][1]["id"] == "marker_toss"

    session.apply_action(
        HumanAction(action_type="discard", payload={"card_indices": [1]})
    )

    hand_ids = [c.get("id") for c in session.state.seats[victim].hand]
    assert "marker_toss" not in hand_ids
    assert "marker_keep" in hand_ids
    assert any(
        e["type"] == "force_discard"
        and e.get("seat") == victim
        and any(d.get("id") == "marker_toss" for d in e.get("discarded") or [])
        for e in session.state.event_log
    )


def test_peek_is_private_to_peeker():
    session = GameSession(
        ["a", "b", "c", "d"],
        ["King", "Noble1", "Noble2", "Noble3"],
        starting_king_seat=0,
        seed=19,
    )
    _pass_negotiation(session)

    cards = {c["id"]: c for c in load_all_cards()}
    intrigue = cards["king_court_intrigue_001"]
    king = 0
    target = 1
    session.state.seats[king].hand = [intrigue, *session.state.seats[king].hand]

    _advance_until(
        session,
        lambda d: d.dtype == DecisionType.TARGET
        and d.context.get("card", {}).get("id") == "king_court_intrigue_001",
        prefer_play_first=king,
        prefer_card_id="king_court_intrigue_001",
    )

    secret = {
        **cards["noble_development_fund_001"],
        "id": "secret_card",
        "name": "Secret Ledger",
    }
    session.state.seats[target].hand = [secret]

    session.apply_action(
        HumanAction(action_type="choose_target", payload={"target_seat": target})
    )

    _advance_until(session, lambda d: d.dtype == DecisionType.REVEAL)
    dec = session.current_decision()
    assert dec is not None and dec.dtype == DecisionType.REVEAL

    peek_events = [e for e in session.state.event_log if e["type"] == "peek_card"]
    assert peek_events
    assert "card" not in peek_events[-1]

    peeker_private = session.build_private_state("a")
    other_private = session.build_private_state("b")
    assert peeker_private.peek is not None
    assert peeker_private.peek["card"]["id"] == "secret_card"
    assert peeker_private.peek["from_seat"] == target
    assert other_private.peek is None
