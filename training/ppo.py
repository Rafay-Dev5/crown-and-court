from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from agents.heuristic.observation import OBS_DIM


@dataclass
class PPOConfig:
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 0.5
    ppo_epochs: int = 4
    minibatch_size: int = 32
    hidden_dim: int = 64


@dataclass
class Transition:
    obs: np.ndarray
    action: int
    log_prob: float
    value: float
    reward: float
    done: bool
    global_obs: np.ndarray | None = None
    seat: int = 0


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    exp = np.exp(x)
    return exp / (np.sum(exp) + 1e-8)


def _one_hot(action: int, dim: int) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    vec[action % dim] = 1.0
    return vec


class PPOPolicy:
    """Actor-critic policy with clipped PPO updates (numpy-only)."""

    def __init__(
        self,
        obs_dim: int = OBS_DIM,
        act_dim: int = 64,
        seed: int = 0,
        config: PPOConfig | None = None,
    ):
        self.config = config or PPOConfig()
        self.obs_dim = obs_dim
        self.act_dim = act_dim
        self.rng = np.random.default_rng(seed)
        h = self.config.hidden_dim
        scale = 0.1
        self.actor_w1 = self.rng.normal(0, scale, (obs_dim, h)).astype(np.float32)
        self.actor_b1 = np.zeros(h, dtype=np.float32)
        self.actor_w2 = self.rng.normal(0, scale, (h, act_dim)).astype(np.float32)
        self.actor_b2 = np.zeros(act_dim, dtype=np.float32)
        self.critic_w1 = self.rng.normal(0, scale, (obs_dim, h)).astype(np.float32)
        self.critic_b1 = np.zeros(h, dtype=np.float32)
        self.critic_w2 = self.rng.normal(0, scale, (h, 1)).astype(np.float32)
        self.critic_b2 = np.zeros(1, dtype=np.float32)
        self._last_hidden: np.ndarray | None = None

    def _actor_forward(self, obs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        obs = obs.astype(np.float32).reshape(-1)
        hidden = np.tanh(obs @ self.actor_w1 + self.actor_b1)
        logits = hidden @ self.actor_w2 + self.actor_b2
        self._last_hidden = hidden
        return logits, _softmax(logits)

    def _critic_forward(self, obs: np.ndarray) -> float:
        obs = obs.astype(np.float32).reshape(-1)
        hidden = np.tanh(obs @ self.critic_w1 + self.critic_b1)
        return float((hidden @ self.critic_w2 + self.critic_b2)[0])

    def act(self, obs: np.ndarray, deterministic: bool = False) -> int:
        action, _ = self.select_action(obs, deterministic=deterministic)
        return action

    def select_action(
        self, obs: np.ndarray, deterministic: bool = False
    ) -> tuple[int, float]:
        _, probs = self._actor_forward(obs)
        if deterministic:
            action = int(np.argmax(probs))
        else:
            action = int(self.rng.choice(self.act_dim, p=probs))
        log_prob = float(np.log(probs[action] + 1e-8))
        return action, log_prob

    def act_with_value(
        self, obs: np.ndarray, deterministic: bool = False
    ) -> tuple[int, float, float]:
        action, log_prob = self.select_action(obs, deterministic)
        value = self._critic_forward(obs)
        return action, log_prob, value

    def evaluate(self, obs: np.ndarray, action: int) -> tuple[float, float, np.ndarray]:
        logits, probs = self._actor_forward(obs)
        value = self._critic_forward(obs)
        log_prob = float(np.log(probs[action % self.act_dim] + 1e-8))
        entropy = -float(np.sum(probs * np.log(probs + 1e-8)))
        return log_prob, value, probs

    def update(self, batch: list[Transition]) -> dict[str, float]:
        if len(batch) < 2:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        cfg = self.config
        rewards = np.array([t.reward for t in batch], dtype=np.float32)
        values = np.array([t.value for t in batch], dtype=np.float32)
        dones = np.array([t.done for t in batch], dtype=np.float32)
        advantages = self._compute_gae(rewards, values, dones)
        returns = advantages + values
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        old_log_probs = np.array([t.log_prob for t in batch], dtype=np.float32)
        obs_batch = np.stack([t.obs for t in batch])
        actions = np.array([t.action % self.act_dim for t in batch], dtype=np.int64)

        policy_losses: list[float] = []
        value_losses: list[float] = []
        entropies: list[float] = []

        indices = np.arange(len(batch))
        for _ in range(cfg.ppo_epochs):
            self.rng.shuffle(indices)
            for start in range(0, len(batch), cfg.minibatch_size):
                mb = indices[start : start + cfg.minibatch_size]
                for idx in mb:
                    obs = obs_batch[idx]
                    action = int(actions[idx])
                    adv = float(advantages[idx])
                    ret = float(returns[idx])
                    old_lp = float(old_log_probs[idx])

                    new_lp, value, probs = self.evaluate(obs, action)
                    ratio = np.exp(new_lp - old_lp)
                    clipped = np.clip(ratio, 1 - cfg.clip_epsilon, 1 + cfg.clip_epsilon)
                    policy_loss = -float(np.minimum(ratio * adv, clipped * adv))

                    value_loss = (value - ret) ** 2
                    entropy = -float(np.sum(probs * np.log(probs + 1e-8)))

                    self._apply_gradients(obs, action, policy_loss, value_loss, entropy, adv, ret, old_lp)

                    policy_losses.append(policy_loss)
                    value_losses.append(value_loss)
                    entropies.append(entropy)

        return {
            "policy_loss": float(np.mean(policy_losses)) if policy_losses else 0.0,
            "value_loss": float(np.mean(value_losses)) if value_losses else 0.0,
            "entropy": float(np.mean(entropies)) if entropies else 0.0,
        }

    def _compute_gae(
        self, rewards: np.ndarray, values: np.ndarray, dones: np.ndarray
    ) -> np.ndarray:
        cfg = self.config
        advantages = np.zeros_like(rewards)
        last_gae = 0.0
        next_value = 0.0
        for t in reversed(range(len(rewards))):
            mask = 1.0 - dones[t]
            delta = rewards[t] + cfg.gamma * next_value * mask - values[t]
            last_gae = delta + cfg.gamma * cfg.gae_lambda * mask * last_gae
            advantages[t] = last_gae
            next_value = values[t]
        return advantages

    def _apply_gradients(
        self,
        obs: np.ndarray,
        action: int,
        policy_loss: float,
        value_loss: float,
        entropy: float,
        advantage: float,
        ret: float,
        old_log_prob: float,
    ) -> None:
        cfg = self.config
        lr = cfg.learning_rate
        obs = obs.astype(np.float32).reshape(-1)

        actor_h = np.tanh(obs @ self.actor_w1 + self.actor_b1)
        logits = actor_h @ self.actor_w2 + self.actor_b2
        probs = _softmax(logits)
        action_idx = action % self.act_dim

        critic_h = np.tanh(obs @ self.critic_w1 + self.critic_b1)
        value = float((critic_h @ self.critic_w2 + self.critic_b2)[0])

        # Policy gradient via softmax cross-entropy surrogate
        d_logits = probs.copy()
        d_logits[action_idx] -= 1.0
        d_logits *= policy_loss * advantage / (probs[action_idx] + 1e-8)

        self.actor_w2 -= lr * np.outer(actor_h, d_logits)
        self.actor_b2 -= lr * d_logits
        d_actor_h = d_logits @ self.actor_w2.T
        d_actor_h *= 1 - actor_h**2
        self.actor_w1 -= lr * np.outer(obs, d_actor_h)
        self.actor_b1 -= lr * d_actor_h

        # Value head
        value_err = 2 * (value - ret) * cfg.value_coef
        self.critic_w2 -= lr * value_err * critic_h.reshape(-1, 1)
        self.critic_b2 -= lr * value_err
        d_critic_h = (self.critic_w2.flatten() * value_err) * (1 - critic_h**2)
        self.critic_w1 -= lr * np.outer(obs, d_critic_h)
        self.critic_b1 -= lr * d_critic_h

        # Entropy bonus (encourage exploration)
        d_entropy = probs * (np.log(probs + 1e-8) + 1)
        self.actor_w2 += lr * cfg.entropy_coef * np.outer(actor_h, d_entropy)
        self.actor_b2 += lr * cfg.entropy_coef * d_entropy


# Backward-compatible alias used by older imports/tests
SimplePolicy = PPOPolicy


def train_step(
    policy: PPOPolicy,
    batch: list[Transition],
    config: PPOConfig | None = None,
) -> float:
    """Run one PPO update on a trajectory batch; returns total loss proxy."""
    _ = config
    stats = policy.update(batch)
    return stats["policy_loss"] + stats["value_loss"]
