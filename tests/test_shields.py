from engine.cards import load_config
from engine.effects.interpreter import resolve_card
from engine.phases import setup_game
from engine.protection import finalize_protection_bets
from engine.rng import GameRNG


def test_ward_whiff_applies_penalty():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    seat = 1
    gold_before = state.person_at_seat(seat).gold
    card = {
        "id": "noble_ward_001",
        "name": "Ward",
        "category": "protection",
        "timing": "reactive",
        "effect": {
            "primitive": "protect_gold",
            "params": {
                "target": "self",
                "amount": 100,
                "duration_rounds": 1,
                "specificity": "generic",
                "trigger": {"type": "attacked_this_phase", "target": "self"},
            },
        },
        "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}},
    }
    resolve_card(state, card, seat, GameRNG(seed=2))
    finalize_protection_bets(state, GameRNG(seed=2))
    assert state.person_at_seat(seat).gold < gold_before
    assert any(e["type"] == "protection_whiff" for e in state.event_log)


def test_king_ward_hits_when_attacked_later_in_phase():
    config = load_config()
    state = setup_game(config, GameRNG(seed=10))
    king = state.king_seat
    noble = state.noble_seats()[0]
    card = {
        "id": "king_treasury_shield_001",
        "category": "protection",
        "effect": {
            "primitive": "protect_gold",
            "params": {
                "target": "self",
                "amount": 150,
                "duration_rounds": 1,
                "trigger": {"type": "attacked_this_phase", "target": "self", "attack_type": "gold_theft"},
            },
        },
        "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}},
    }
    resolve_card(state, card, king, GameRNG(seed=1))
    from engine.effects.primitives import gold_transfer

    ctx = {
        "seat": noble,
        "target_seat": king,
        "card_id": "noble_blackmail_001",
        "params": {"from": "king", "to": "self", "amount": 50, "as_theft": True},
    }
    gold_transfer(state, ctx, GameRNG(seed=2))
    finalize_protection_bets(state, GameRNG(seed=3))
    assert any(e["type"] == "protection_hit" for e in state.event_log)
    assert any(e["type"] == "shield_blocked" for e in state.event_log)
