from engine.cards import load_all_cards, load_config
from engine.effects.interpreter import resolve_card
from engine.phases import setup_game
from engine.rng import GameRNG
from engine.state import StatusTag
from engine.status_ticks import CORRUPT_DRIP_AMOUNT, apply_status_tick_effects


def test_dice_swing_stipend_branch_no_roll():
    config = load_config()
    state = setup_game(config, GameRNG(seed=10))
    king = state.king_seat
    target = state.noble_seats()[0]
    noble_before = state.person_at_seat(target).gold
    king_before = state.person_at_seat(king).gold
    card = {
        "id": "test_stipend",
        "name": "Test",
        "effect": {
            "primitive": "dice_swing",
            "params": {
                "choice_seat": "target",
                "choices": [{"id": "stipend", "label": "Stipend"}],
                "branches": {
                    "stipend": {
                        "on_success": {
                            "primitive": "gold_gain",
                            "params": {"target": "target", "amount": 40},
                            "secondary_effect": {
                                "primitive": "gold_gain",
                                "params": {"target": "self", "amount": 80},
                            },
                        }
                    }
                },
            },
        },
    }
    resolve_card(state, card, king, GameRNG(seed=1), target_seat=target, selected_choice="stipend")
    assert len(state.dice_log) == 0
    assert state.person_at_seat(target).gold == noble_before + 40
    assert state.person_at_seat(king).gold == king_before + 80


def test_corrupt_status_tick_transfers_to_king():
    config = load_config()
    state = setup_game(config, GameRNG(seed=2))
    noble = state.noble_seats()[0]
    king = state.king_seat
    state.seats[noble].statuses.append(
        StatusTag(name="corrupt", expires_after_round=state.current_round + 2)
    )
    noble_before = state.person_at_seat(noble).gold
    king_before = state.person_at_seat(king).gold
    apply_status_tick_effects(state, GameRNG(seed=3))
    transfer = min(CORRUPT_DRIP_AMOUNT, noble_before)
    assert state.person_at_seat(king).gold == king_before + transfer
    assert state.person_at_seat(noble).gold == noble_before - transfer


class _FixedRoll:
    def __init__(self, roll: int) -> None:
        self.roll = roll

    def randint(self, _low: int, _high: int) -> int:
        return self.roll


def test_tithe_gamble_success_pays_the_noble():
    config = load_config()
    state = setup_game(config, GameRNG(seed=4))
    king = state.king_seat
    target = state.noble_seats()[0]
    cards = {c["id"]: c for c in load_all_cards()}
    card = cards["king_tithe_of_silence_001"]
    noble_before = state.person_at_seat(target).gold
    king_before = state.person_at_seat(king).gold
    resolve_card(
        state,
        card,
        king,
        _FixedRoll(6),
        target_seat=target,
        selected_choice="gamble",
    )
    assert state.dice_log[-1].success is True
    assert state.person_at_seat(target).gold == noble_before + 150
    assert state.person_at_seat(king).gold == king_before
    assert all(st.name != "corrupt" for st in state.seats[target].statuses)


def test_tithe_gamble_failure_pays_the_king_and_corrupts():
    config = load_config()
    state = setup_game(config, GameRNG(seed=5))
    king = state.king_seat
    target = state.noble_seats()[0]
    cards = {c["id"]: c for c in load_all_cards()}
    card = cards["king_tithe_of_silence_001"]
    noble_before = state.person_at_seat(target).gold
    king_before = state.person_at_seat(king).gold
    resolve_card(
        state,
        card,
        king,
        _FixedRoll(4),
        target_seat=target,
        selected_choice="gamble",
    )
    assert state.dice_log[-1].success is False
    assert state.person_at_seat(target).gold == noble_before - 100
    assert state.person_at_seat(king).gold == king_before + 100
    assert any(st.name == "corrupt" for st in state.seats[target].statuses)


def test_tithe_of_silence_card_valid_and_present():
    cards = {c["id"]: c for c in load_all_cards()}
    assert "king_tithe_of_silence_001" in cards
    assert "king_treasury_dividend_001" not in cards
    tithe = cards["king_tithe_of_silence_001"]
    assert tithe["effect"]["params"]["choice_seat"] == "target"
    assert "stipend" in tithe["effect"]["params"]["branches"]
    assert "gamble" in tithe["effect"]["params"]["branches"]
