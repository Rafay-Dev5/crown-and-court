"""Trade card previews and confirm-before-accept for gold↔card deals."""

from __future__ import annotations

from engine.cards import load_config
from engine.negotiation import accept_proposal, confirm_proposal, propose_trade
from engine.phases import setup_game
from engine.rng import GameRNG
from web.server.game_session import GameSession, HumanAction


def test_cards_for_gold_attaches_card_details_for_receiver():
    state = setup_game(load_config(), GameRNG(seed=3))
    seller = 0
    buyer = 1
    card = state.seats[seller].hand[0]
    pid = propose_trade(
        state,
        seller,
        buyer,
        {"gold": 0, "cards": [card["id"]]},
        {"gold": 30, "card_count": 0},
    )
    prop = next(p for p in state.pending_proposals if p["id"] == pid)
    details = prop["offer"].get("card_details") or []
    assert len(details) == 1
    assert details[0]["id"] == card["id"]
    assert details[0]["name"] == card.get("name")


def test_gold_for_cards_requires_proposer_confirm_on_web():
    session = GameSession(
        ["a", "b", "c", "d"],
        ["King", "Noble1", "Noble2", "Noble3"],
        starting_king_seat=0,
        seed=5,
    )
    assert session.state.config.get("pause_between_reveals") is True
    buyer = 0
    seller = 1
    card = session.state.seats[seller].hand[0]
    gold_buyer = session.state.person_at_seat(buyer).gold

    pid = propose_trade(
        session.state,
        buyer,
        seller,
        {"gold": 80, "cards": []},
        {"gold": 0, "card_count": 1},
    )
    ok = accept_proposal(session.state, seller, pid, fulfillment_cards=[card["id"]])
    assert ok
    prop = next(p for p in session.state.pending_proposals if p["id"] == pid)
    assert prop["status"] == "pending_confirm"
    details = prop["request"].get("card_details") or []
    assert details[0]["id"] == card["id"]
    # Trade not executed yet.
    assert session.state.person_at_seat(buyer).gold == gold_buyer
    assert any(c.get("id") == card["id"] for c in session.state.seats[seller].hand)

    pub = session.build_public_state()
    assert any(p.get("id") == pid and p.get("status") == "pending_confirm" for p in pub.pending_proposals)

    assert confirm_proposal(session.state, buyer, pid)
    assert session.state.person_at_seat(buyer).gold == gold_buyer - 80
    assert any(c.get("id") == card["id"] for c in session.state.seats[buyer].hand)
    assert not any(c.get("id") == card["id"] for c in session.state.seats[seller].hand)
