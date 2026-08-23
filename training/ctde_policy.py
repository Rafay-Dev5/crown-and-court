"""CTDE shared GRU actor + centralized critic (numpy PPO)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from agents.heuristic.observation import ACTOR_INPUT_DIM, GLOBAL_OBS_DIM
from training.ppo import PPOConfig, Transition, _softmax, train_step


class SharedGRUPolicy:
    """One shared actor (local obs + seat embed) and centralized critic (global state)."""

    def __init__(
        self,
        act_dim: int = 64,
        seed: int = 0,
        config: PPOConfig | None = None,
    ):
        self.config = config or PPOConfig()
        self.act_dim = act_dim
        self.actor_input_dim = ACTOR_INPUT_DIM
        self.global_obs_dim = GLOBAL_OBS_DIM
        self.rng = np.random.default_rng(seed)
        h = self.config.hidden_dim
        scale = 0.08

        self.gru_w_x = self.rng.normal(0, scale, (self.actor_input_dim, h)).astype(np.float32)
        self.gru_w_h = self.rng.normal(0, scale, (h, h)).astype(np.float32)
        self.gru_b = np.zeros(h, dtype=np.float32)
        self.actor_w2 = self.rng.normal(0, scale, (h, act_dim)).astype(np.float32)
        self.actor_b2 = np.zeros(act_dim, dtype=np.float32)

        self.critic_w1 = self.rng.normal(0, scale, (self.global_obs_dim, h)).astype(np.float32)
        self.critic_b1 = np.zeros(h, dtype=np.float32)
        self.critic_w2 = self.rng.normal(0, scale, (h, 1)).astype(np.float32)
        self.critic_b2 = np.zeros(1, dtype=np.float32)

        self.hidden: dict[int, np.ndarray] = {}
        self._last_hidden: np.ndarray | None = None
        self._last_seat: int | None = None

    def reset_hidden(self, seat: int | None = None) -> None:
        if seat is None:
            self.hidden.clear()
        else:
            self.hidden.pop(seat, None)

    def _get_hidden(self, seat: int) -> np.ndarray:
        h = self.config.hidden_dim
        if seat not in self.hidden:
            self.hidden[seat] = np.zeros(h, dtype=np.float32)
        return self.hidden[seat]

    def _encode(self, actor_obs: np.ndarray, seat: int) -> np.ndarray:
        x = actor_obs.astype(np.float32).reshape(-1)
        prev = self._get_hidden(seat)
        pre = x @ self.gru_w_x + prev @ self.gru_w_h + self.gru_b
        hidden = np.tanh(pre)
        self.hidden[seat] = hidden
        self._last_hidden = hidden
        self._last_seat = seat
        return hidden

    def _critic_value(self, global_obs: np.ndarray) -> float:
        g = global_obs.astype(np.float32).reshape(-1)
        hidden = np.tanh(g @ self.critic_w1 + self.critic_b1)
        return float((hidden @ self.critic_w2 + self.critic_b2)[0])

    def _actor_probs(self, actor_obs: np.ndarray, seat: int) -> tuple[np.ndarray, np.ndarray]:
        hidden = self._encode(actor_obs, seat)
        logits = hidden @ self.actor_w2 + self.actor_b2
        return logits, _softmax(logits)

    def act_with_value(
        self,
        actor_obs: np.ndarray,
        global_obs: np.ndarray,
        seat: int,
        deterministic: bool = False,
    ) -> tuple[int, float, float]:
        _, probs = self._actor_probs(actor_obs, seat)
        if deterministic:
            action = int(np.argmax(probs))
        else:
            action = int(self.rng.choice(self.act_dim, p=probs))
        log_prob = float(np.log(probs[action] + 1e-8))
        value = self._critic_value(global_obs)
        return action, log_prob, value

    def evaluate(
        self,
        actor_obs: np.ndarray,
        global_obs: np.ndarray,
        seat: int,
        action: int,
    ) -> tuple[float, float, np.ndarray]:
        _, probs = self._actor_probs(actor_obs, seat)
        action_idx = action % self.act_dim
        log_prob = float(np.log(probs[action_idx] + 1e-8))
        value = self._critic_value(global_obs)
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

        policy_losses: list[float] = []
        value_losses: list[float] = []
        entropies: list[float] = []

        indices = np.arange(len(batch))
        for _ in range(cfg.ppo_epochs):
            self.rng.shuffle(indices)
            for idx in indices:
                t = batch[idx]
                seat = int(getattr(t, "seat", 0))
                global_obs = getattr(t, "global_obs", None)
                if global_obs is None:
                    global_obs = t.obs
                new_lp, value, probs = self.evaluate(t.obs, global_obs, seat, t.action)
                ratio = np.exp(new_lp - old_log_probs[idx])
                clipped = np.clip(ratio, 1 - cfg.clip_epsilon, 1 + cfg.clip_epsilon)
                policy_loss = -float(np.minimum(ratio * advantages[idx], clipped * advantages[idx]))
                value_loss = (value - returns[idx]) ** 2
                entropy = -float(np.sum(probs * np.log(probs + 1e-8)))
                self._apply_gradients(t.obs, global_obs, seat, t.action, policy_loss, value_loss, advantages[idx], returns[idx])
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
        actor_obs: np.ndarray,
        global_obs: np.ndarray,
        seat: int,
        action: int,
        policy_loss: float,
        value_loss: float,
        advantage: float,
        ret: float,
    ) -> None:
        cfg = self.config
        lr = cfg.learning_rate
        x = actor_obs.astype(np.float32).reshape(-1)
        g = global_obs.astype(np.float32).reshape(-1)

        hidden = self._encode(actor_obs, seat)
        logits = hidden @ self.actor_w2 + self.actor_b2
        probs = _softmax(logits)
        action_idx = action % self.act_dim

        d_logits = probs.copy()
        d_logits[action_idx] -= 1.0
        d_logits *= policy_loss * advantage / (probs[action_idx] + 1e-8)
        self.actor_w2 -= lr * np.outer(hidden, d_logits)
        self.actor_b2 -= lr * d_logits
        d_hidden = d_logits @ self.actor_w2.T
        d_hidden *= 1 - hidden**2
        self.gru_w_x -= lr * np.outer(x, d_hidden)
        prev = self._get_hidden(seat)
        self.gru_w_h -= lr * np.outer(prev, d_hidden)
        self.gru_b -= lr * d_hidden

        critic_h = np.tanh(g @ self.critic_w1 + self.critic_b1)
        value = float((critic_h @ self.critic_w2 + self.critic_b2)[0])
        value_err = 2 * (value - ret) * cfg.value_coef
        self.critic_w2 -= lr * value_err * critic_h.reshape(-1, 1)
        self.critic_b2 -= lr * value_err
        d_critic_h = (self.critic_w2.flatten() * value_err) * (1 - critic_h**2)
        self.critic_w1 -= lr * np.outer(g, d_critic_h)
        self.critic_b1 -= lr * d_critic_h

        d_entropy = probs * (np.log(probs + 1e-8) + 1)
        self.actor_w2 += lr * cfg.entropy_coef * np.outer(hidden, d_entropy)
        self.actor_b2 += lr * cfg.entropy_coef * d_entropy

    def weights_dict(self) -> dict[str, Any]:
        return {
            "act_dim": self.act_dim,
            "config": {
                "learning_rate": self.config.learning_rate,
                "hidden_dim": self.config.hidden_dim,
            },
            "arrays": {k: v.tolist() for k, v in self.__dict__.items() if isinstance(v, np.ndarray)},
        }

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.weights_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str, seed: int = 0) -> SharedGRUPolicy:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg = PPOConfig(**data.get("config", {}))
        policy = cls(act_dim=int(data["act_dim"]), seed=seed, config=cfg)
        for name, arr in data.get("arrays", {}).items():
            if hasattr(policy, name):
                setattr(policy, name, np.array(arr, dtype=np.float32))
        return policy

    def clone_frozen(self) -> SharedGRUPolicy:
        """Deep copy for league checkpoints (no weight sharing)."""
        clone = SharedGRUPolicy(act_dim=self.act_dim, seed=0, config=self.config)
        for name, val in self.__dict__.items():
            if isinstance(val, np.ndarray):
                setattr(clone, name, val.copy())
            elif name == "hidden":
                clone.hidden = {}
            elif name == "rng":
                continue
            else:
                setattr(clone, name, val)
        return clone


def build_shared_policy(config: dict, seed: int = 0) -> SharedGRUPolicy:
    act_dim = int(config.get("policy_act_dim", 64))
    ppo_cfg = PPOConfig(
        learning_rate=float(config.get("learning_rate", 3e-4)),
        hidden_dim=int(config.get("policy_hidden_dim", 64)),
    )
    return SharedGRUPolicy(act_dim=act_dim, seed=seed, config=ppo_cfg)


def train_shared_step(policy: SharedGRUPolicy, batch: list[Transition]) -> float:
    stats = policy.update(batch)
    return stats["policy_loss"] + stats["value_loss"]
