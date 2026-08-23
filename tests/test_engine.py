import pytest

from engine.cards import load_all_cards, load_config
from engine.negotiation import accept_proposal, propose_trade
from engine.phases import run_game, setup_game
from engine.rng import GameRNG
from engine.state import Phase, Role
from engine.succession import earned_gold_eligible, perform_seat_swap, resolve_succession


def test_setup_creates_valid_state():
    config = load_config()
    config["num_players"] = 4
    config["n_rounds"] = 2
    rng = GameRNG(seed=1)
    state = setup_game(config, rng)
    assert state.num_players == 4
    assert state.king_seat == 0
    assert state.seats[0].role == Role.KING
    assert len(state.seats[0].hand) == 8
    assert state.person_at_seat(0).gold == 1000


def test_full_game_runs_to_completion():
    config = load_config()
    config["num_players"] = 4
    config["n_rounds"] = 2
    rng = GameRNG(seed=42)
    state = run_game(config, rng)
    assert state.phase == Phase.GAME_END
    assert any(e["type"] == "game_end" for e in state.event_log)


def test_earned_gold_succession():
    config = load_config()
    rng = GameRNG(seed=7)
    state = setup_game(config, rng)
    noble_seat = state.noble_seats()[0]
    state.person_at_seat(noble_seat).earned_gold = 2000
    state.person_at_seat(noble_seat).gold = 2000
    assert earned_gold_eligible(state, noble_seat)
    ascending = resolve_succession(state, "earned_gold")
    assert ascending == noble_seat


def test_seat_swap_keeps_gold_with_person():
    config = load_config()
    rng = GameRNG(seed=7)
    state = setup_game(config, rng)
    king_seat = state.king_seat
    noble_seat = state.noble_seats()[0]
    king_person = state.seats[king_seat].person_id
    noble_person = state.seats[noble_seat].person_id
    king_gold_before = state.players[king_person].gold
    noble_gold_before = state.players[noble_person].gold
    king_hand_len = len(state.seats[king_seat].hand)
    perform_seat_swap(state, noble_seat)
    assert state.king_seat == noble_seat
    assert state.players[king_person].gold == king_gold_before
    assert state.players[noble_person].gold == noble_gold_before
    assert len(state.seats[noble_seat].hand) == king_hand_len


def test_gifted_gold_does_not_count_for_succession():
    config = load_config()
    rng = GameRNG(seed=9)
    state = setup_game(config, rng)
    noble_seat = state.noble_seats()[0]
    king_seat = state.king_seat
    noble = state.person_at_seat(noble_seat)
    king = state.person_at_seat(king_seat)
    noble.gold = king.earned_gold + 500
    noble.gifted_gold = 500
    assert noble.earned_gold <= king.earned_gold
    assert not earned_gold_eligible(state, noble_seat)


def test_negotiation_trade_tracks_gifted_gold():
    config = load_config()
    rng = GameRNG(seed=3)
    state = setup_game(config, rng)
    proposer = 0
    target = 1
    pid = propose_trade(state, proposer, target, {"gold": 100}, {"gold": 0})
    accept_proposal(state, target, pid)
    assert state.person_at_seat(target).gifted_gold >= 100


def test_negotiation_phase_gift_cap():
    config = load_config()
    config["max_negotiation_gift"] = 100
    config["max_negotiation_gift_per_phase"] = 150
    rng = GameRNG(seed=3)
    state = setup_game(config, rng)
    proposer = 0
    target_a = 1
    target_b = 2
    pid = propose_trade(state, proposer, target_a, {"gold": 100}, {"gold": 0})
    accept_proposal(state, target_a, pid)
    pid2 = propose_trade(state, proposer, target_b, {"gold": 100}, {"gold": 0})
    accept_proposal(state, target_b, pid2)
    assert state.person_at_seat(target_a).gifted_gold == 100
    assert state.person_at_seat(target_b).gifted_gold == 50


def test_negotiation_trade_per_trade_cap():
    config = load_config()
    config["max_negotiation_gift"] = 200
    config["max_negotiation_gift_per_trade"] = 50
    config["max_negotiation_gift_per_phase"] = 500
    rng = GameRNG(seed=7)
    state = setup_game(config, rng)
    proposer = 0
    target = 1
    pid = propose_trade(state, proposer, target, {"gold": 150}, {"gold": 120})
    accept_proposal(state, target, pid)
    assert state.person_at_seat(target).gifted_gold == 50
    assert state.person_at_seat(proposer).gifted_gold == 50


def test_gold_transfer_preserves_gifted_ledger():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    victim = 1
    thief = 2
    person = state.person_at_seat(victim)
    person.gold = 500
    person.earned_gold = 100
    person.gifted_gold = 400
    thief_person = state.person_at_seat(thief)
    thief_person.earned_gold = 0
    thief_person.gifted_gold = 0
    from engine.effects.primitives import gold_transfer

    ctx = {
        "seat": thief,
        "target_seat": victim,
        "card_id": "test_theft",
        "params": {"from": "target", "to": "self", "amount": 200, "as_theft": True},
    }
    gold_transfer(state, ctx, GameRNG(seed=2))
    receiver = state.person_at_seat(thief)
    assert receiver.earned_gold == 100
    assert receiver.gifted_gold == 100


def test_random_starting_king_seat():
    config = load_config()
    config["num_players"] = 6
    config["n_rounds"] = 2
    config["random_starting_king_seat"] = True
    seats_seen: set[int] = set()
    for seed in range(30):
        state = setup_game(config, GameRNG(seed=seed))
        seats_seen.add(state.king_seat)
        setup_evt = next(e for e in state.event_log if e["type"] == "game_setup")
        assert setup_evt["starting_king_seat"] == state.king_seat
        assert state.seats[state.king_seat].role == Role.KING
        assert state.person_at_seat(state.king_seat).gold == config["king_start_gold"]
    assert len(seats_seen) >= 3


def test_cards_load():
    cards = load_all_cards()
    assert len(cards) >= 10
