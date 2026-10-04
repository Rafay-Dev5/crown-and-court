"""Imperial Edict and Royal Pardon: you gain, the chosen opponent pays."""

from engine.cards import load_all_cards, load_config
from engine.effects.interpreter import resolve_card
from engine.phases import card_requires_chosen_target, setup_game
from engine.rng import GameRNG


def _cards():
    return {c["id"]: c for c in load_all_cards()}


def test_imperial_edict_pays_you_and_charges_the_opponent():
    card = _cards()["king_imperial_edict_001"]
    assert card_requires_chosen_target(card)
    state = setup_game(load_config(), GameRNG(seed=1))
    king = state.king_seat
    target = state.noble_seats()[0]
    king_before = state.person_at_seat(king).gold
    target_before = state.person_at_seat(target).gold
    resolve_card(state, card, king, GameRNG(seed=2), target_seat=target)
    assert state.person_at_seat(king).gold == king_before + 170
    assert state.person_at_seat(target).gold == target_before - 110


def test_royal_pardon_pays_you_and_charges_the_opponent():
    card = _cards()["king_royal_pardon_001"]
    assert card_requires_chosen_target(card)
    state = setup_game(load_config(), GameRNG(seed=3))
    king = state.king_seat
    target = state.noble_seats()[1]
    king_before = state.person_at_seat(king).gold
    target_before = state.person_at_seat(target).gold
    resolve_card(state, card, king, GameRNG(seed=4), target_seat=target)
    assert state.person_at_seat(king).gold == king_before + 120
    assert state.person_at_seat(target).gold == target_before - 90
