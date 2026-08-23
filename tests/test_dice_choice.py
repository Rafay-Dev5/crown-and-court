import pytest

from engine.cards import load_config
from engine.effects.interpreter import resolve_card
from engine.phases import setup_game
from engine.rng import GameRNG
from engine.state import ChoiceRecord, DiceRecord


def test_roll_die_logs_result():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    seat = 1
    ctx_card = {
        "id": "test_die",
        "name": "Test",
        "effect": {"primitive": "roll_die", "params": {"sides": 6, "target_min": 4}},
    }
    resolve_card(state, ctx_card, seat, GameRNG(seed=99))
    assert len(state.dice_log) == 1
    assert state.dice_log[0].sides == 6


def test_dice_swing_records_choice_and_roll():
    config = load_config()
    rng = GameRNG(seed=50)
    state = setup_game(config, rng)
    seat = state.noble_seats()[0]
    card = {
        "id": "test_swing",
        "name": "Test Swing",
        "effect": {
            "primitive": "dice_swing",
            "params": {
                "choices": [
                    {"id": "invest_public", "label": "Public"},
                    {"id": "invest_private", "label": "Private"},
                ],
                "branches": {
                    "invest_public": {
                        "die": {"sides": 6, "target_min": 4},
                        "on_success": {"primitive": "gold_gain", "params": {"target": "self", "amount": 100}},
                        "on_failure": {"primitive": "gold_loss", "params": {"target": "self", "amount": 50}},
                    }
                },
            },
        },
    }
    gold_before = state.person_at_seat(seat).gold
    resolve_card(state, card, seat, rng, selected_choice="invest_public")
    assert any(c.choice_id == "invest_public" for c in state.choice_log)
    assert len(state.dice_log) == 1
    assert state.person_at_seat(seat).gold != gold_before or state.dice_log[0].success


def test_prior_choice_within():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    state.current_round = 3
    state.choice_log.append(
        ChoiceRecord(round=2, phase="playing", card_id="c1", choice_id="invest_private", seat=2)
    )
    assert state.prior_choice_within(2, "invest_private", 2)
    assert not state.prior_choice_within(2, "invest_private", 1)


def test_development_fund_card_from_json():
    from engine.cards import load_all_cards

    cards = {c["id"]: c for c in load_all_cards()}
    assert "noble_development_fund_001" in cards
    assert cards["noble_development_fund_001"]["effect"]["primitive"] == "dice_swing"
