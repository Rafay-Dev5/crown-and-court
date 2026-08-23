import pytest

from engine.decisions import DecisionEngine
from engine.rng import GameRNG
from engine.cards import load_config
from env.crown_court_env import CrownCourtEnv


def test_decision_engine_runs_to_end():
    config = load_config()
    config["num_players"] = 4
    config["n_rounds"] = 1
    config["hand_size"] = 4
    config["negotiation_ticks"] = 2
    engine = DecisionEngine(config, GameRNG(seed=1))
    engine.reset()
    steps = 0
    max_steps = 3000
    while not engine.done and steps < max_steps:
        engine.step(0)
        steps += 1
    assert engine.done
    assert steps < max_steps


def test_pettingzoo_env_reset_step():
    env = CrownCourtEnv(
        config={"num_players": 4, "n_rounds": 1, "hand_size": 4, "negotiation_ticks": 2},
        seed=42,
    )
    env.reset(seed=42)
    steps = 0
    max_steps = 3000
    while env.agents and steps < max_steps:
        agent = env.agent_selection
        action = env.action_spaces[agent].sample()
        env.step(action)
        steps += 1
    assert steps < max_steps
    assert all(env.terminations.values())
