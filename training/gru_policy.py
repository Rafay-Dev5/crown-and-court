from __future__ import annotations

import numpy as np

from agents.heuristic.observation import OBS_DIM
from training.ppo import PPOConfig, PPOPolicy, _softmax


class GRUPolicy(PPOPolicy):
    """Single-layer GRU actor-critic (numpy) for partial observability."""

    def __init__(
        self,
        obs_dim: int = OBS_DIM,
        act_dim: int = 64,
        seed: int = 0,
        config: PPOConfig | None = None,
    ):
        super().__init__(obs_dim, act_dim, seed, config)
        h = self.config.hidden_dim
        scale = 0.08
        self.gru_w_x = self.rng.normal(0, scale, (obs_dim, h)).astype(np.float32)
        self.gru_w_h = self.rng.normal(0, scale, (h, h)).astype(np.float32)
        self.gru_b = np.zeros(h, dtype=np.float32)
        self.hidden = np.zeros(h, dtype=np.float32)

    def reset_hidden(self) -> None:
        self.hidden = np.zeros_like(self.hidden)

    def _encode(self, obs: np.ndarray) -> np.ndarray:
        obs = obs.astype(np.float32).reshape(-1)
        pre = obs @ self.gru_w_x + self.hidden @ self.gru_w_h + self.gru_b
        self.hidden = np.tanh(pre)
        return self.hidden

    def _forward(self, obs: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        hidden = self._encode(obs)
        logits = hidden @ self.actor_w2 + self.actor_b2
        probs = _softmax(logits)
        value = float((hidden @ self.critic_w2 + self.critic_b2)[0])
        self._last_hidden = hidden
        return logits, probs, value

    def _actor_forward(self, obs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        logits, probs, _ = self._forward(obs)
        return logits, probs

    def _critic_forward(self, obs: np.ndarray) -> float:
        _, _, value = self._forward(obs)
        return value

    def act_with_value(
        self, obs: np.ndarray, deterministic: bool = False
    ) -> tuple[int, float, float]:
        _, probs, value = self._forward(obs)
        if deterministic:
            action = int(np.argmax(probs))
        else:
            action = int(self.rng.choice(self.act_dim, p=probs))
        log_prob = float(np.log(probs[action] + 1e-8))
        return action, log_prob, value

    def evaluate(self, obs: np.ndarray, action: int) -> tuple[float, float, np.ndarray]:
        _, probs, value = self._forward(obs)
        action_idx = action % self.act_dim
        log_prob = float(np.log(probs[action_idx] + 1e-8))
        entropy = -float(np.sum(probs * np.log(probs + 1e-8)))
        return log_prob, value, probs


def build_policy(config: dict, seat: int, seed: int) -> PPOPolicy:
    if config.get("use_ctde", True):
        from training.policy_factory import build_policy

        return build_policy(config, seed=seed)
    policy_type = str(config.get("policy_type", "mlp")).lower()
    if policy_type == "gru":
        return GRUPolicy(seed=seed + seat)
    return PPOPolicy(seed=seed + seat)
