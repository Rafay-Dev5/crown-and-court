"""Hands over the cap are discarded before the redraw, which is King 3 and Noble 2."""

from engine.state import Alliance, PendingProtectionBet
from web.server.game_session import GameSession, HumanAction


def _card(name: str) -> dict:
    return {
        "id": name,
        "name": name,
        "category": "economy",
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 1}},
    }


def test_over_cap_discard_happens_before_the_smaller_redraw():
    session = GameSession(["a", "b", "c", "d"], ["A", "B", "C", "D"], starting_king_seat=0, seed=3)
    while session.current_decision() and session.current_decision().dtype.value == "negotiation":
        session.apply_action(HumanAction(action_type="pass"))

    king = session.state.king_seat
    nobles = [seat for seat in range(session.state.num_players) if seat != king]
    # King is over 8. One noble is exactly at 7. The others are over 7.
    session.state.seats[king].hand = [_card(f"k{i}") for i in range(9)]
    session.state.seats[nobles[0]].hand = [_card(f"n0-{i}") for i in range(7)]
    session.state.seats[nobles[1]].hand = [_card(f"n1-{i}") for i in range(8)]
    session.state.seats[nobles[2]].hand = [_card(f"n2-{i}") for i in range(8)]
    decks = {seat: len(session.state.seats[seat].deck) for seat in range(4)}

    while session.current_decision() and session.current_decision().dtype.value == "play":
        session.apply_action(HumanAction(action_type="play", payload={"card_indices": []}))

    dec = session.current_decision()
    assert dec is not None and dec.dtype.value == "discard"
    assert dec.context.get("reason") == "hand_limit"
    assert dec.seat == king
    assert dec.context["count"] == 1
    assert len(session.state.seats[king].deck) == decks[king]

    session.apply_action(
        HumanAction(action_type="discard", payload={"card_indices": [0]})
    )
    # Still trimming. The King's redraw has not happened yet.
    assert len(session.state.seats[king].hand) == 8
    assert len(session.state.seats[king].deck) == decks[king]
    assert session.current_decision().dtype.value == "discard"

    while session.current_decision() and session.current_decision().dtype.value == "discard":
        count = int(session.current_decision().context["count"])
        session.apply_action(
            HumanAction(action_type="discard", payload={"card_indices": list(range(count))})
        )

    assert len(session.state.seats[king].hand) == 11
    assert len(session.state.seats[king].deck) == decks[king] - 3
    assert len(session.state.seats[nobles[0]].hand) == 9
    assert len(session.state.seats[nobles[0]].deck) == decks[nobles[0]] - 2
    assert len(session.state.seats[nobles[1]].hand) == 9
    assert len(session.state.seats[nobles[2]].hand) == 9


def test_final_round_skips_discard_redraw_and_alliance_review():
    session = GameSession(["a", "b", "c", "d"], ["A", "B", "C", "D"], starting_king_seat=0, seed=4)
    while session.current_decision() and session.current_decision().dtype.value == "negotiation":
        session.apply_action(HumanAction(action_type="pass"))

    session.state.current_round = session.state.n_rounds
    king = session.state.king_seat
    ally = next(seat for seat in range(session.state.num_players) if seat != king)
    session.state.seats[king].hand = [_card(f"k{i}") for i in range(9)]
    session.state.alliances.append(
        Alliance(members=frozenset({king, ally}), declared_round=session.state.current_round)
    )
    deck_before = len(session.state.seats[king].deck)

    while session.current_decision() and session.current_decision().dtype.value == "play":
        session.apply_action(HumanAction(action_type="play", payload={"card_indices": []}))

    dec = session.current_decision()
    assert dec is None or dec.dtype.value not in ("discard", "alliance")
    assert session.state.phase.value == "game_end"
    assert len(session.state.seats[king].hand) == 9
    assert len(session.state.seats[king].deck) == deck_before
    assert any(frozenset({king, ally}) == alliance.members for alliance in session.state.alliances)


def test_end_of_round_settles_before_the_new_king_discards():
    session = GameSession(["a", "b", "c", "d"], ["A", "B", "C", "D"], starting_king_seat=0, seed=5)
    while session.current_decision() and session.current_decision().dtype.value == "negotiation":
        session.apply_action(HumanAction(action_type="pass"))

    state = session.state
    king = state.king_seat
    rich = next(seat for seat in range(state.num_players) if seat != king)
    others = [seat for seat in range(state.num_players) if seat not in (king, rich)]
    king_gold = state.person_at_seat(king).gold
    state.person_at_seat(rich).gold = king_gold + 4000
    king_deck = len(state.seats[king].deck)
    noble_deck = len(state.seats[rich].deck)
    # The crown's hand is 9. After succession that hand belongs to the new King.
    state.seats[king].hand = [_card(f"k{i}") for i in range(9)]
    state.seats[rich].hand = [_card(f"r{i}") for i in range(7)]
    for seat in others:
        state.seats[seat].hand = [_card(f"o{seat}-{i}") for i in range(7)]
    state.alliances.append(Alliance(members=frozenset({king, rich}), declared_round=state.current_round))
    state.note_betrayal(king, rich, "broken oath")
    state.apply_status(rich, "corrupt", 2)
    state.pending_protection_bets.append(
        PendingProtectionBet(
            seat=others[0],
            card_id="test_ward",
            card={"id": "test_ward"},
            trigger={"type": "attacked_this_phase", "target": "self"},
            target_seat=others[0],
        )
    )

    while session.current_decision() and session.current_decision().dtype.value == "play":
        session.apply_action(HumanAction(action_type="play", payload={"card_indices": []}))

    types = [event["type"] for event in state.event_log]
    ended = types.index("alliance_ended")
    tick = types.index("status_tick")
    whiff = types.index("protection_whiff")
    crowned = types.index("succession")
    assert ended < tick < whiff < crowned
    assert state.king_seat == rich
    assert state.person_at_seat(king).gold == king_gold + 100
    assert state.person_at_seat(rich).gold == king_gold + 3900
    assert not any(
        event.get("reason") in ("Alliance stipend", "Alliance with the King")
        for event in state.event_log
        if event["type"] == "gold_gain"
    )

    dec = session.current_decision()
    assert dec is not None and dec.dtype.value == "discard"
    assert dec.seat == rich
    assert dec.context["cap"] == 8
    assert dec.context["count"] == 1
    assert len(state.seats[rich].hand) == 9
    assert len(state.seats[rich].deck) == king_deck
    assert len(state.seats[king].hand) == 7

    session.apply_action(HumanAction(action_type="discard", payload={"card_indices": [0]}))
    assert session.current_decision() is None or session.current_decision().dtype.value != "discard"
    assert len(state.seats[rich].hand) == 11
    assert len(state.seats[rich].deck) == king_deck - 3
    assert len(state.seats[king].hand) == 9
    assert len(state.seats[king].deck) == noble_deck - 2
