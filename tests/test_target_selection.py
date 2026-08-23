"""Interactive card targeting for web sessions."""

from __future__ import annotations

from engine.cards import load_all_cards
from engine.decisions import DecisionType
from engine.phases import card_requires_chosen_target
from web.server.game_session import GameSession, HumanAction


def test_tithe_requires_chosen_target():
    cards = {c["id"]: c for c in load_all_cards()}
    tithe = cards["king_tithe_of_silence_001"]
    assert card_requires_chosen_target(tithe)


def test_player_chooses_card_target_before_resolve():
    session = GameSession(
        ["a", "b", "c", "d"],
        ["King", "Noble1", "Noble2", "Noble3"],
        starting_king_seat=0,
        seed=7,
    )
    # Skip negotiation.
    while session.current_decision() and session.current_decision().dtype == DecisionType.NEGOTIATION:
        session.apply_action(HumanAction(action_type="pass"))

    # Force the king to play Tithe of Silence as their first reveal card.
    king = session.state.king_seat
    cards = {c["id"]: c for c in load_all_cards()}
    tithe = cards["king_tithe_of_silence_001"]
    session.state.seats[king].hand = [tithe, *session.state.seats[king].hand]

    dec = session.current_decision()
    assert dec is not None and dec.dtype == DecisionType.PLAY
    assert dec.seat == king
    n = int(dec.context.get("n_play", 3))
    session.apply_action(
        HumanAction(action_type="play", payload={"card_indices": list(range(n))})
    )

    # Other seats lock in so reveals begin.
    while True:
        dec = session.current_decision()
        assert dec is not None
        if dec.dtype == DecisionType.TARGET:
            break
        if dec.dtype == DecisionType.PLAY:
            n = int(dec.context.get("n_play", 2))
            session.apply_action(
                HumanAction(action_type="play", payload={"card_indices": list(range(n))})
            )
            continue
        if dec.dtype == DecisionType.REVEAL:
            session.apply_action(HumanAction(action_type="continue_reveal"))
            continue
        if dec.dtype == DecisionType.CHOICE:
            session.apply_action(
                HumanAction(action_type="choice", payload={"choice_index": 0})
            )
            continue
        if dec.dtype == DecisionType.NEGOTIATION:
            session.apply_action(HumanAction(action_type="pass"))
            continue
        break

    dec = session.current_decision()
    assert dec is not None
    assert dec.dtype == DecisionType.TARGET
    assert dec.seat == king
    assert dec.context.get("card", {}).get("id") == "king_tithe_of_silence_001"
    legal = list(dec.context.get("legal_targets") or [])
    assert set(legal) == {1, 2, 3}

    # Aim at seat 2 specifically — not the auto-default first noble.
    chosen = 2
    session.apply_action(
        HumanAction(action_type="choose_target", payload={"target_seat": chosen})
    )

    dec = session.current_decision()
    assert dec is not None
    assert dec.dtype == DecisionType.CHOICE
    # Tithe: the targeted opponent chooses the path.
    assert dec.seat == chosen
    assert dec.context.get("target_seat") == chosen
    assert dec.context.get("card_seat") == king


def test_reveal_hand_event_includes_card_summaries():
    from engine.cards import load_config
    from engine.effects.interpreter import resolve_card
    from engine.phases import setup_game
    from engine.rng import GameRNG

    state = setup_game(load_config(), GameRNG(seed=3))
    king = state.king_seat
    target = state.noble_seats()[0]
    assert state.seats[target].hand
    card = {
        "id": "test_scandal",
        "name": "Test Scandal",
        "effect": {"primitive": "reveal_hand", "params": {"target": "target"}},
    }
    resolve_card(state, card, king, GameRNG(seed=4), target_seat=target)
    events = [e for e in state.event_log if e["type"] == "reveal_hand"]
    assert events
    cards = events[-1]["cards"]
    assert isinstance(cards, list) and cards
    assert all(isinstance(c, dict) and c.get("name") for c in cards)
