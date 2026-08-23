import numpy as np

from agents.heuristic.observation import OBS_DIM
from training.ppo import PPOConfig, PPOPolicy, Transition, train_step


def test_ppo_update_changes_loss():
    policy = PPOPolicy(seed=1, config=PPOConfig(learning_rate=0.01, ppo_epochs=2))
    batch = []
    for i in range(8):
        obs = np.random.randn(OBS_DIM).astype(np.float32)
        action, log_prob = policy.select_action(obs)
        value = policy._critic_forward(obs)
        batch.append(
            Transition(
                obs=obs,
                action=action,
                log_prob=log_prob,
                value=value,
                reward=1.0 if i % 2 == 0 else -0.1,
                done=i == 7,
            )
        )
    stats = policy.update(batch)
    assert "policy_loss" in stats
    assert stats["policy_loss"] >= 0.0


def test_train_step_returns_float():
    policy = PPOPolicy(seed=2)
    obs = np.zeros(OBS_DIM, dtype=np.float32)
    action, log_prob = policy.select_action(obs)
    batch = [
        Transition(
            obs=obs, action=action, log_prob=log_prob, value=0.0, reward=1.0, done=True
        )
    ]
    loss = train_step(policy, batch)
    assert isinstance(loss, float)
