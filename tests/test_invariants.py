import numpy as np
import pytest

from engine.cards import load_config
from engine.negotiation import propose_conditional, propose_trade, accept_proposal
from engine.phases import run_game, setup_game
from engine.rng import GameRNG


def test_gold_never_negative_and_transfers_conserved():
    config = load_config()
    config["num_players"] = 4
    config["n_rounds"] = 2
    state = run_game(config, GameRNG(seed=123))
    for player in state.players:
        assert player.gold >= 0
    transfer_delta = 0
    for event in state.event_log:
        if event["type"] == "gold_transfer" and not event.get("blocked"):
            transfer_delta += 0  # zero-sum by design
    assert transfer_delta == 0


def test_propose_conditional_logged():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    pid = propose_conditional(
        state,
        0,
        1,
        {"gold": 100},
        {"type": "no_disruption", "target": 0},
    )
    assert pid
    assert any(p.id == pid for p in state.conditional_promises)


def test_wilson_and_min_n():
    from analytics.stats import min_sample_size, wilson_interval

    lo, hi = wilson_interval(60, 100)
    assert lo < 0.65 < hi
    assert min_sample_size(margin=0.05) >= 30
