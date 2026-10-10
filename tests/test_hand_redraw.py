"""Hands over the cap are discarded before the redraw, which is King 3 and Noble 2."""

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
