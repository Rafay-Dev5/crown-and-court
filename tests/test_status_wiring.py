from engine.cards import load_all_cards, load_config
from engine.effects.interpreter import resolve_card
from engine.negotiation import accept_proposal, propose_trade
from engine.phases import setup_game
from engine.rng import GameRNG
from engine.state import StatusTag


def _cards_by_id():
    return {card["id"]: card for card in load_all_cards()}


def test_sealed_warrant_gets_marked_bonus():
    cards = _cards_by_id()
    card = cards["king_sealed_warrant_001"]

    base_state = setup_game(load_config(), GameRNG(seed=1))
    base_king = base_state.king_seat
    base_target = base_state.noble_seats()[0]
    base_king_before = base_state.person_at_seat(base_king).gold
    base_target_before = base_state.person_at_seat(base_target).gold
    resolve_card(base_state, card, base_king, GameRNG(seed=2), target_seat=base_target)

    marked_state = setup_game(load_config(), GameRNG(seed=3))
    marked_king = marked_state.king_seat
    marked_target = marked_state.noble_seats()[0]
    marked_state.seats[marked_target].statuses.append(
        StatusTag(name="marked", expires_after_round=marked_state.current_round + 2)
    )
    marked_king_before = marked_state.person_at_seat(marked_king).gold
    marked_target_before = marked_state.person_at_seat(marked_target).gold
    resolve_card(marked_state, card, marked_king, GameRNG(seed=4), target_seat=marked_target)

    assert base_state.person_at_seat(base_king).gold == base_king_before + 80
    assert base_state.person_at_seat(base_target).gold == base_target_before - 80
    assert marked_state.person_at_seat(marked_king).gold == marked_king_before + 100
    assert marked_state.person_at_seat(marked_target).gold == marked_target_before - 100


def test_oathbreaker_blocks_negotiation_gifts():
    state = setup_game(load_config(), GameRNG(seed=5))
    giver = state.king_seat
    receiver = state.noble_seats()[0]
    state.seats[receiver].statuses.append(
        StatusTag(name="oathbreaker", expires_after_round=state.current_round + 2)
    )
    card = state.seats[receiver].hand[0]
    gold_before = state.person_at_seat(receiver).gold
    proposal_id = propose_trade(
        state, giver, receiver, {"gold": 100, "cards": []}, {"gold": 0, "card_count": 1}
    )
    accept_proposal(state, receiver, proposal_id, fulfillment_cards=[card["id"]])

    assert state.person_at_seat(receiver).gold == gold_before
    assert any(
        event["type"] == "gift_blocked_by_status" and event["status"] == "oathbreaker"
        for event in state.event_log
    )


def test_unbalanced_gold_for_cards_applies_oathbreaker():
    """100g for 1 card (40): seller 100 vs buyer 40 → 40 ≤ 50 → seller OB."""
    state = setup_game(load_config(), GameRNG(seed=12))
    buyer = state.king_seat
    seller = state.noble_seats()[0]
    card = state.seats[seller].hand[0]
    proposal_id = propose_trade(
        state, buyer, seller, {"gold": 100, "cards": []}, {"gold": 0, "card_count": 1}
    )
    accept_proposal(state, seller, proposal_id, fulfillment_cards=[card["id"]])

    assert not state.has_status(buyer, "oathbreaker")
    assert state.has_status(seller, "oathbreaker")


def test_buyer_41g_for_two_cards_avoids_oathbreaker():
    """41g for 2 cards (80): 41 > half of 80 → neither branded."""
    state = setup_game(load_config(), GameRNG(seed=15))
    buyer = state.king_seat
    seller = state.noble_seats()[0]
    cards = [c["id"] for c in state.seats[seller].hand[:2]]
    proposal_id = propose_trade(
        state, buyer, seller, {"gold": 41, "cards": []}, {"gold": 0, "card_count": 2}
    )
    accept_proposal(state, seller, proposal_id, fulfillment_cards=cards)

    assert not state.has_status(buyer, "oathbreaker")
    assert not state.has_status(seller, "oathbreaker")


def test_underpriced_card_deal_brands_buyer_only():
    """20g for 1 card (40): buyer 40 vs seller 20 → 20 ≤ 20 → buyer OB."""
    state = setup_game(load_config(), GameRNG(seed=16))
    buyer = state.king_seat
    seller = state.noble_seats()[0]
    card = state.seats[seller].hand[0]
    proposal_id = propose_trade(
        state, buyer, seller, {"gold": 20, "cards": []}, {"gold": 0, "card_count": 1}
    )
    accept_proposal(state, seller, proposal_id, fulfillment_cards=[card["id"]])

    assert state.has_status(buyer, "oathbreaker")
    assert not state.has_status(seller, "oathbreaker")


def test_fair_priced_card_deal_brands_neither():
    """40g for 1 card: equal values — neither branded."""
    state = setup_game(load_config(), GameRNG(seed=17))
    buyer = state.king_seat
    seller = state.noble_seats()[0]
    card = state.seats[seller].hand[0]
    proposal_id = propose_trade(
        state, buyer, seller, {"gold": 40, "cards": []}, {"gold": 0, "card_count": 1}
    )
    accept_proposal(state, seller, proposal_id, fulfillment_cards=[card["id"]])

    assert not state.has_status(buyer, "oathbreaker")
    assert not state.has_status(seller, "oathbreaker")


def test_71g_for_one_card_brands_neither():
    """71g for 1 card (40): 40 > half of 71 → neither branded."""
    state = setup_game(load_config(), GameRNG(seed=18))
    seller = state.king_seat
    buyer = state.noble_seats()[0]
    card = state.seats[seller].hand[0]
    proposal_id = propose_trade(
        state, seller, buyer, {"gold": 0, "cards": [card["id"]]}, {"gold": 71, "cards": []}
    )
    accept_proposal(state, buyer, proposal_id)

    assert not state.has_status(seller, "oathbreaker")
    assert not state.has_status(buyer, "oathbreaker")


def test_cards_for_cards_imbalance_brands_receiver():
    state = setup_game(load_config(), GameRNG(seed=14))
    a = state.king_seat
    b = state.noble_seats()[0]
    offer_card = state.seats[a].hand[0]
    take = [c["id"] for c in state.seats[b].hand[:4]]
    proposal_id = propose_trade(
        state,
        a,
        b,
        {"gold": 0, "cards": [offer_card["id"]]},
        {"gold": 0, "card_count": 4},
    )
    accept_proposal(state, b, proposal_id, fulfillment_cards=take)

    assert state.has_status(a, "oathbreaker")
    assert not state.has_status(b, "oathbreaker")


def test_royal_census_forces_discredited_target_to_discard():
    cards = _cards_by_id()
    card = cards["king_royal_edict_28_028"]
    state = setup_game(load_config(), GameRNG(seed=6))
    king = state.king_seat
    target = state.noble_seats()[0]
    hand_before = len(state.seats[target].hand)
    state.seats[target].statuses.append(
        StatusTag(name="discredited", expires_after_round=state.current_round + 2)
    )

    resolve_card(state, card, king, GameRNG(seed=7), target_seat=target)

    assert len(state.seats[target].hand) == hand_before - 1
    assert any(event["type"] == "reveal_hand" and event["seat"] == target for event in state.event_log)
    assert any(event["type"] == "force_discard" and event["seat"] == target for event in state.event_log)


def test_development_fund_two_cook_the_books_skips_die_and_marks_corrupt():
    cards = _cards_by_id()
    card = cards["noble_development_fund_001"]
    state = setup_game(load_config(), GameRNG(seed=8))
    seat = state.noble_seats()[0]
    before_gold = state.person_at_seat(seat).gold

    resolve_card(
        state,
        card,
        seat,
        GameRNG(seed=9),
        target_seat=state.king_seat,
        selected_choice="cook_the_books",
    )

    assert len(state.dice_log) == 0
    assert state.person_at_seat(seat).gold == before_gold + 70
    assert state.has_status(seat, "corrupt")


def test_broken_crown_applies_oathbreaker_to_target():
    cards = _cards_by_id()
    card = cards["king_broken_crown_001"]
    state = setup_game(load_config(), GameRNG(seed=10))
    king = state.king_seat
    target = state.noble_seats()[0]

    resolve_card(state, card, king, GameRNG(seed=11), target_seat=target)

    assert state.has_status(target, "oathbreaker")
