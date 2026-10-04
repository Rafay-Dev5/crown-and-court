"""End-of-round alliance stipend, paid after succession and before renewal."""

from engine.cards import load_config
from engine.phases import pay_alliance_stipend, run_succession_check, setup_game
from engine.rng import GameRNG
from engine.state import Alliance


def _state():
    config = load_config()
    config["num_players"] = 4
    return setup_game(config, GameRNG(seed=1))


def test_two_nobles_each_gain_100():
    state = _state()
    a, b = 1, 2
    state.alliances.append(Alliance(members=frozenset({a, b}), declared_round=1))
    before = {seat: state.person_at_seat(seat).gold for seat in range(4)}
    pay_alliance_stipend(state)
    assert state.person_at_seat(a).gold == before[a] + 100
    assert state.person_at_seat(b).gold == before[b] + 100
    assert state.person_at_seat(0).gold == before[0]
    assert state.person_at_seat(3).gold == before[3]


def test_an_alliance_with_the_king_pays_150_each():
    state = _state()
    king, noble = state.king_seat, 1
    state.alliances.append(Alliance(members=frozenset({king, noble}), declared_round=1))
    before_king = state.person_at_seat(king).gold
    before_noble = state.person_at_seat(noble).gold
    pay_alliance_stipend(state)
    assert state.person_at_seat(king).gold == before_king + 150
    assert state.person_at_seat(noble).gold == before_noble + 150
    reasons = [e["reason"] for e in state.event_log if e["type"] == "gold_gain"]
    assert reasons == ["Alliance with the King", "Alliance with the King"]


def test_a_betrayal_that_already_ended_the_alliance_pays_nothing():
    state = _state()
    a, b = 1, 2
    state.alliances.append(Alliance(members=frozenset({a, b}), declared_round=1))
    before = state.person_at_seat(a).gold
    state.note_betrayal(a, b, "betrayal")
    state.apply_pending_betrayals()
    pay_alliance_stipend(state)
    assert state.person_at_seat(a).gold == before
    assert not any(e["type"] == "gold_gain" for e in state.event_log)


def test_stipend_uses_the_king_before_succession():
    state = _state()
    rising, partner = 1, 2
    state.alliances.append(Alliance(members=frozenset({rising, partner}), declared_round=1))
    state.person_at_seat(rising).gold = state.person_at_seat(state.king_seat).gold + 1
    before_rising = state.person_at_seat(rising).gold
    before_partner = state.person_at_seat(partner).gold
    pay_alliance_stipend(state)
    assert state.king_seat != rising
    assert state.person_at_seat(rising).gold == before_rising + 100
    assert state.person_at_seat(partner).gold == before_partner + 100
    run_succession_check(state)
    assert state.king_seat == rising
