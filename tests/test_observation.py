import tempfile
from pathlib import Path

import numpy as np
import pytest
import yaml

from agents.heuristic.observation import OBS_DIM, seat_observation
from analytics.metrics import compute_metrics
from analytics.sweeps import run_sweep
from engine.cards import load_config
from engine.phases import setup_game
from engine.rng import GameRNG


def test_observation_dim_matches_config():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    obs = seat_observation(state, 0)
    assert obs.shape == (OBS_DIM,)
    assert obs.dtype == np.float32


def test_assisted_win_rate_person_matched():
    logs = [
        [
            {"type": "game_setup", "starting_king_person": 0, "starting_king_seat": 0},
            {"type": "gold_gifted", "to_seat": 2, "to_person": 2, "from_seat": 1, "from_person": 1, "amount": 50},
            {"type": "game_end", "winner_seat": 0, "winner_person": 0},
        ],
        [
            {"type": "game_setup", "starting_king_person": 0, "starting_king_seat": 0},
            {"type": "gold_gifted", "to_seat": 0, "to_person": 0, "from_seat": 1, "from_person": 1, "amount": 50},
            {"type": "game_end", "winner_seat": 0, "winner_person": 0},
        ],
    ]
    m = compute_metrics(logs)
    assert m["assisted_win_rate"] == 0.5
    assert m["assisted_win_rate_seat"] == 0.5


def test_reward_shaping_disabled_in_sweeps():
    bad = load_config("configs/balance.yaml")
    bad["reward_shaping"] = True
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.yaml"
        path.write_text(yaml.safe_dump(bad), encoding="utf-8")
        with pytest.raises(AssertionError, match="reward_shaping"):
            run_sweep(str(path), games=1, seed=0)
