from engine.cards import load_config
from engine.effects.interpreter import resolve_card
from engine.phases import setup_game
from engine.rng import GameRNG
from engine.state import Alliance


def _vow(name: str) -> dict:
    return {
        "id": name,
        "name": name,
        "category": "betrayal",
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "target", "to": "self", "amount": 30, "as_theft": True},
        },
        "requires_state": {"alliance_declared_with_target": True},
    }


def test_betrayal_against_an_ally_resolves_and_alliance_lasts_until_phase_end():
    state = setup_game(load_config(), GameRNG(seed=1))
    betrayer, ally = 1, 2
    state.alliances.append(Alliance(members=frozenset({betrayer, ally}), declared_round=1))
    ally_gold = state.person_at_seat(ally).gold
    betrayer_gold = state.person_at_seat(betrayer).gold

    resolve_card(state, _vow("Broken Vow"), betrayer, GameRNG(seed=2), target_seat=ally)
    resolve_card(state, _vow("Backstab"), betrayer, GameRNG(seed=3), target_seat=ally)

    assert not any(e["type"] == "card_fizzled" for e in state.event_log)
    assert not any(e["type"] == "card_precondition_failed" for e in state.event_log)
    assert state.has_alliance_between(betrayer, ally)
    assert state.person_at_seat(ally).gold == ally_gold - 60
    assert state.person_at_seat(betrayer).gold == betrayer_gold + 60

    state.apply_pending_betrayals()
    assert not state.has_alliance_between(betrayer, ally)
    assert any(e["type"] == "alliance_ended" for e in state.event_log)


def test_alliance_card_hits_the_ally_even_if_another_target_was_passed():
    from engine.phases import card_requires_chosen_target

    state = setup_game(load_config(), GameRNG(seed=8))
    player, ally, other = 0, 1, 2
    state.alliances.append(Alliance(members=frozenset({player, ally}), declared_round=1))
    card = {
        "id": "noble_mob_contract_001",
        "name": "Mob Contract",
        "category": "alliance",
        "effect": {
            "primitive": "alliance_bonus",
            "params": {"amount": 55, "players": ["self", "target"]},
        },
    }
    assert not card_requires_chosen_target(card)
    before_ally = state.person_at_seat(ally).gold
    before_other = state.person_at_seat(other).gold
    resolve_card(state, card, player, GameRNG(seed=9), target_seat=other)
    assert not any(e["type"] == "card_fizzled" for e in state.event_log)
    assert state.person_at_seat(ally).gold == before_ally + 55
    assert state.person_at_seat(other).gold == before_other


def test_betrayal_without_an_alliance_fizzles():
    state = setup_game(load_config(), GameRNG(seed=4))
    betrayer, other = 1, 2
    gold = state.person_at_seat(other).gold
    resolve_card(state, _vow("Broken Vow"), betrayer, GameRNG(seed=5), target_seat=other)
    assert any(e["type"] == "card_fizzled" for e in state.event_log)
    assert state.person_at_seat(other).gold == gold
    state.apply_pending_betrayals()
    assert state.pending_betrayals == []
