"""Revolution Banner pays the noble who leads the other nobles."""

from __future__ import annotations

import json
from pathlib import Path

from engine.card_text import describe_card_full_lines
from engine.cards import load_config
from engine.effects.interpreter import resolve_card
from engine.phases import setup_game
from engine.rng import GameRNG

CARD = json.loads(
    Path("cards/noble_deck/revolution_banner.json").read_text(encoding="utf-8")
)


def _state():
    config = load_config()
    config["num_players"] = 4
    return setup_game(config, GameRNG(seed=2))


def test_banner_text_names_the_noble_gold_check():
    text = "\n".join(describe_card_full_lines(CARD))
    assert "more gold than every other Noble" in text
    assert "gain 200 gold" in text
    assert "lose 150 gold" in text
    assert "special condition" not in text


def test_leading_noble_gains_200_even_when_the_king_has_more():
    state = _state()
    nobles = state.noble_seats()
    leader = nobles[0]
    state.person_at_seat(state.king_seat).gold = 5000
    state.person_at_seat(leader).gold = 900
    for seat in nobles[1:]:
        state.person_at_seat(seat).gold = 400
    resolve_card(state, CARD, leader, GameRNG(seed=3))
    assert state.person_at_seat(leader).gold == 1100


def test_tie_for_the_lead_pays_the_150_penalty():
    state = _state()
    nobles = state.noble_seats()
    player = nobles[0]
    state.person_at_seat(player).gold = 800
    state.person_at_seat(nobles[1]).gold = 800
    state.person_at_seat(nobles[2]).gold = 100
    resolve_card(state, CARD, player, GameRNG(seed=4))
    assert state.person_at_seat(player).gold == 650


def test_richer_than_the_king_but_not_the_other_nobles_pays_the_penalty():
    state = _state()
    nobles = state.noble_seats()
    player = nobles[0]
    state.person_at_seat(state.king_seat).gold = 100
    state.person_at_seat(player).gold = 700
    state.person_at_seat(nobles[1]).gold = 900
    state.person_at_seat(nobles[2]).gold = 200
    resolve_card(state, CARD, player, GameRNG(seed=5))
    assert state.person_at_seat(player).gold == 550
