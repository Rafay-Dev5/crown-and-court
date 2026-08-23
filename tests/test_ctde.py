import numpy as np

from agents.heuristic.observation import ACTOR_INPUT_DIM, GLOBAL_OBS_DIM, actor_observation, global_observation
from engine.cards import load_config
from engine.phases import setup_game
from engine.rng import GameRNG
from training.ctde_policy import SharedGRUPolicy, build_shared_policy
from training.benchmark import run_benchmarks


def test_shared_gru_act_and_update():
    policy = SharedGRUPolicy(seed=1, config=__import__("training.ppo", fromlist=["PPOConfig"]).PPOConfig(ppo_epochs=1))
    ao = np.random.randn(ACTOR_INPUT_DIM).astype(np.float32)
    go = np.random.randn(GLOBAL_OBS_DIM).astype(np.float32)
    action, log_prob, value = policy.act_with_value(ao, go, seat=2)
    assert 0 <= action < policy.act_dim
    assert isinstance(value, float)

    from training.ppo import Transition

    batch = []
    for i in range(6):
        batch.append(
            Transition(
                obs=ao,
                global_obs=go,
                seat=2,
                action=action,
                log_prob=log_prob,
                value=value,
                reward=1.0 if i % 2 == 0 else -0.1,
                done=i == 5,
            )
        )
    stats = policy.update(batch)
    assert "policy_loss" in stats


def test_actor_and_global_obs_shapes():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    ao = actor_observation(state, 0)
    go = global_observation(state, 0)
    assert ao.shape == (ACTOR_INPUT_DIM,)
    assert go.shape == (GLOBAL_OBS_DIM,)


def test_benchmark_smoke():
    config = load_config("configs/training.yaml")
    policy = build_shared_policy(config, seed=3)
    result = run_benchmarks(policy, "configs/training.yaml", games=4, seed=99)
    assert "skill_gap" in result
    assert "exploitability" in result
    assert result["league_eval"]["games"] == 4
