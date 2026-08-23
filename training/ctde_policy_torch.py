"""CTDE shared GRU actor + centralized critic — PyTorch GPU PPO."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from agents.heuristic.observation import ACTOR_INPUT_DIM, GLOBAL_OBS_DIM
from training.ppo import PPOConfig, Transition


def resolve_device(requested: str | None = None) -> torch.device:
    if requested == "cpu":
        return torch.device("cpu")
    if requested and requested.startswith("cuda") and torch.cuda.is_available():
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class _ActorCriticNet(nn.Module):
    def __init__(self, act_dim: int, hidden_dim: int, actor_layers: int = 2, critic_layers: int = 2):
        super().__init__()
        self.act_dim = act_dim
        self.hidden_dim = hidden_dim
        self.gru = nn.GRU(ACTOR_INPUT_DIM, hidden_dim, batch_first=True)
        self.actor_head = nn.Linear(hidden_dim, act_dim)

        critic_blocks: list[nn.Module] = [nn.Linear(GLOBAL_OBS_DIM, hidden_dim), nn.Tanh()]
        for _ in range(critic_layers - 1):
            critic_blocks.extend([nn.Linear(hidden_dim, hidden_dim), nn.Tanh()])
        critic_blocks.append(nn.Linear(hidden_dim, 1))
        self.critic = nn.Sequential(*critic_blocks)

    def critic_forward(self, global_obs: torch.Tensor) -> torch.Tensor:
        return self.critic(global_obs).squeeze(-1)

    def actor_logits(self, actor_obs: torch.Tensor, hidden: torch.Tensor | None) -> tuple[torch.Tensor, torch.Tensor]:
        if actor_obs.dim() == 2:
            actor_obs = actor_obs.unsqueeze(1)
        out, new_hidden = self.gru(actor_obs, hidden)
        logits = self.actor_head(out[:, -1, :])
        return logits, new_hidden


class TorchSharedGRUPolicy:
    """GPU-accelerated CTDE policy with batched PPO updates."""

    def __init__(
        self,
        act_dim: int = 64,
        config: PPOConfig | None = None,
        device: torch.device | None = None,
        seed: int = 0,
        critic_layers: int = 2,
    ):
        self.config = config or PPOConfig()
        self.act_dim = act_dim
        self.critic_layers = critic_layers
        self.device = device or resolve_device()
        self.actor_input_dim = ACTOR_INPUT_DIM
        self.global_obs_dim = GLOBAL_OBS_DIM
        self.net = _ActorCriticNet(
            act_dim=act_dim,
            hidden_dim=self.config.hidden_dim,
            critic_layers=critic_layers,
        ).to(self.device)
        self._rng = np.random.default_rng(seed)
        self.hidden: dict[int, torch.Tensor] = {}

    def reset_hidden(self, seat: int | None = None) -> None:
        if seat is None:
            self.hidden.clear()
        else:
            self.hidden.pop(seat, None)

    def _get_hidden(self, seat: int) -> torch.Tensor | None:
        h = self.hidden.get(seat)
        if h is None:
            return None
        return h

    def act_with_value(
        self,
        actor_obs: np.ndarray,
        global_obs: np.ndarray,
        seat: int,
        deterministic: bool = False,
    ) -> tuple[int, float, float]:
        self.net.eval()
        with torch.no_grad():
            ao = torch.as_tensor(actor_obs, dtype=torch.float32, device=self.device).unsqueeze(0)
            go = torch.as_tensor(global_obs, dtype=torch.float32, device=self.device).unsqueeze(0)
            hidden = self._get_hidden(seat)
            logits, new_hidden = self.net.actor_logits(ao, hidden)
            self.hidden[seat] = new_hidden
            probs = F.softmax(logits, dim=-1).squeeze(0)
            value = self.net.critic_forward(go).squeeze()
            if deterministic:
                action = int(torch.argmax(probs).item())
            else:
                action = int(torch.multinomial(probs, 1).item())
            log_prob = float(torch.log(probs[action] + 1e-8).item())
            return action, log_prob, float(value.item())

    def update(self, batch: list[Transition] | list[list[Transition]]) -> dict[str, float]:
        trajectories = batch if batch and isinstance(batch[0], list) else [batch]  # type: ignore[list-item]
        flat: list[Transition] = [t for traj in trajectories for t in traj]
        if len(flat) < 2:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        cfg = self.config
        rewards = np.array([t.reward for t in flat], dtype=np.float32)
        values = np.array([t.value for t in flat], dtype=np.float32)
        dones = np.array([t.done for t in flat], dtype=np.float32)
        advantages = self._compute_gae(rewards, values, dones)
        returns = advantages + values
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        old_log_probs = np.array([t.log_prob for t in flat], dtype=np.float32)

        actor_obs = torch.as_tensor(np.stack([t.obs for t in flat]), dtype=torch.float32, device=self.device)
        global_obs = torch.as_tensor(
            np.stack([t.global_obs if t.global_obs is not None else t.obs for t in flat]),
            dtype=torch.float32,
            device=self.device,
        )
        actions = torch.as_tensor([t.action % self.act_dim for t in flat], dtype=torch.long, device=self.device)
        adv_t = torch.as_tensor(advantages, dtype=torch.float32, device=self.device)
        ret_t = torch.as_tensor(returns, dtype=torch.float32, device=self.device)
        old_lp_t = torch.as_tensor(old_log_probs, dtype=torch.float32, device=self.device)

        self.net.train()
        optimizer = torch.optim.Adam(self.net.parameters(), lr=cfg.learning_rate)
        policy_losses: list[float] = []
        value_losses: list[float] = []
        entropies: list[float] = []

        n = len(flat)
        mb = max(cfg.minibatch_size, 1)
        indices = np.arange(n)

        for _ in range(cfg.ppo_epochs):
            self._rng.shuffle(indices)
            for start in range(0, n, mb):
                mb_idx = indices[start : start + mb]
                idx_t = torch.as_tensor(mb_idx, dtype=torch.long, device=self.device)
                mb_actor = actor_obs[idx_t]
                mb_global = global_obs[idx_t]
                mb_actions = actions[idx_t]
                mb_adv = adv_t[idx_t]
                mb_ret = ret_t[idx_t]
                mb_old_lp = old_lp_t[idx_t]

                logits, _ = self.net.actor_logits(mb_actor, None)
                probs = F.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs=probs)
                new_lp = dist.log_prob(mb_actions)
                entropy = dist.entropy().mean()
                ratio = torch.exp(new_lp - mb_old_lp)
                clipped = torch.clamp(ratio, 1 - cfg.clip_epsilon, 1 + cfg.clip_epsilon)
                policy_loss = -torch.min(ratio * mb_adv, clipped * mb_adv).mean()

                values = self.net.critic_forward(mb_global)
                value_loss = F.mse_loss(values, mb_ret)

                loss = policy_loss + cfg.value_coef * value_loss - cfg.entropy_coef * entropy
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), cfg.max_grad_norm)
                optimizer.step()

                policy_losses.append(float(policy_loss.item()))
                value_losses.append(float(value_loss.item()))
                entropies.append(float(entropy.item()))

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

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pt_path = path.with_suffix(".pt")
        meta = {
            "backend": "torch",
            "act_dim": self.act_dim,
            "critic_layers": self.critic_layers,
            "config": {
                "learning_rate": self.config.learning_rate,
                "hidden_dim": self.config.hidden_dim,
                "gamma": self.config.gamma,
                "gae_lambda": self.config.gae_lambda,
                "clip_epsilon": self.config.clip_epsilon,
                "value_coef": self.config.value_coef,
                "entropy_coef": self.config.entropy_coef,
                "ppo_epochs": self.config.ppo_epochs,
                "minibatch_size": self.config.minibatch_size,
            },
            "weights_file": pt_path.name,
        }
        torch.save(self.net.state_dict(), pt_path)
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str, device: torch.device | None = None) -> TorchSharedGRUPolicy:
        path = Path(path)
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta.get("backend") != "torch":
            return cls.from_numpy_checkpoint(path, device=device)
        cfg = PPOConfig(**meta.get("config", {}))
        policy = cls(
            act_dim=int(meta["act_dim"]),
            config=cfg,
            device=device,
            critic_layers=int(meta.get("critic_layers", 2)),
        )
        pt_path = path.parent / meta.get("weights_file", path.with_suffix(".pt").name)
        policy.net.load_state_dict(torch.load(pt_path, map_location=policy.device, weights_only=True))
        return policy

    @classmethod
    def from_numpy_checkpoint(
        cls,
        path: Path | str,
        device: torch.device | None = None,
        target_config: dict[str, Any] | None = None,
    ) -> TorchSharedGRUPolicy:
        """Warm-start torch policy from legacy numpy JSON checkpoint."""
        from training.ctde_policy import SharedGRUPolicy

        numpy_policy = SharedGRUPolicy.load(path)
        tc = target_config or {}
        cfg = PPOConfig(
            learning_rate=float(tc.get("learning_rate", numpy_policy.config.learning_rate)),
            hidden_dim=int(tc.get("policy_hidden_dim", numpy_policy.config.hidden_dim)),
            ppo_epochs=int(tc.get("ppo_epochs", numpy_policy.config.ppo_epochs)),
            minibatch_size=int(tc.get("ppo_minibatch_size", numpy_policy.config.minibatch_size)),
        )
        policy = cls(act_dim=numpy_policy.act_dim, config=cfg, device=device)
        h = cfg.hidden_dim
        arrays = {k: np.array(v, dtype=np.float32) for k, v in numpy_policy.weights_dict()["arrays"].items()}

        with torch.no_grad():
            if "critic_w1" in arrays:
                w1 = arrays["critic_w1"]
                h_old, in_old = w1.shape[1], w1.shape[0]
                policy.net.critic[0].weight.data[:h_old, :in_old] = torch.as_tensor(
                    w1.T, device=policy.device
                )
            if "critic_b1" in arrays:
                h_old = arrays["critic_b1"].shape[0]
                policy.net.critic[0].bias.data[:h_old] = torch.as_tensor(
                    arrays["critic_b1"], device=policy.device
                )
            if "critic_w2" in arrays and len(policy.net.critic) >= 3:
                w2 = arrays["critic_w2"]
                last = policy.net.critic[-1]
                h_out, h_in = w2.shape[1], w2.shape[0]
                last.weight.data[:h_out, :h_in] = torch.as_tensor(w2.T, device=policy.device)
                if "critic_b2" in arrays:
                    last.bias.data[: arrays["critic_b2"].shape[0]] = torch.as_tensor(
                        arrays["critic_b2"], device=policy.device
                    )
            if "actor_w2" in arrays:
                w = arrays["actor_w2"]
                policy.net.actor_head.weight.data[: w.shape[1], : w.shape[0]] = torch.as_tensor(
                    w.T, device=policy.device
                )
            if "actor_b2" in arrays:
                policy.net.actor_head.bias.data[: arrays["actor_b2"].shape[0]] = torch.as_tensor(
                    arrays["actor_b2"], device=policy.device
                )
        return policy

    def clone_frozen(self) -> TorchSharedGRUPolicy:
        clone = TorchSharedGRUPolicy(
            act_dim=self.act_dim,
            config=self.config,
            device=torch.device("cpu"),
            critic_layers=self.critic_layers,
        )
        clone.net.load_state_dict(self.net.state_dict())
        clone.net.eval()
        return clone

    def to_numpy_policy(self):
        """Export for league / legacy benchmark compatibility."""
        from training.ctde_policy import SharedGRUPolicy

        out = SharedGRUPolicy(act_dim=self.act_dim, config=self.config)
        h = self.config.hidden_dim
        with torch.no_grad():
            gru = self.net.gru
            out.gru_w_x = gru.weight_ih_l0.cpu().numpy().T[:ACTOR_INPUT_DIM, :h].astype(np.float32)
            out.gru_w_h = gru.weight_hh_l0.cpu().numpy().T[:h, :h].astype(np.float32)
            out.gru_b = (gru.bias_ih_l0 + gru.bias_hh_l0).cpu().numpy()[:h].astype(np.float32)
            out.actor_w2 = self.net.actor_head.weight.cpu().numpy().T.astype(np.float32)
            out.actor_b2 = self.net.actor_head.bias.cpu().numpy().astype(np.float32)
            out.critic_w1 = self.net.critic[0].weight.cpu().numpy().T.astype(np.float32)
            out.critic_b1 = self.net.critic[0].bias.cpu().numpy().astype(np.float32)
            out.critic_w2 = self.net.critic[-1].weight.cpu().numpy().T.astype(np.float32)
            out.critic_b2 = self.net.critic[-1].bias.cpu().numpy().astype(np.float32)
        return out


def build_torch_policy(config: dict[str, Any], seed: int = 0) -> TorchSharedGRUPolicy:
    ppo_cfg = PPOConfig(
        learning_rate=float(config.get("learning_rate", 3e-4)),
        hidden_dim=int(config.get("policy_hidden_dim", 128)),
        ppo_epochs=int(config.get("ppo_epochs", 4)),
        minibatch_size=int(config.get("ppo_minibatch_size", 256)),
        gamma=float(config.get("gamma", 0.99)),
        gae_lambda=float(config.get("gae_lambda", 0.95)),
    )
    device = resolve_device(config.get("device"))
    return TorchSharedGRUPolicy(
        act_dim=int(config.get("policy_act_dim", 64)),
        config=ppo_cfg,
        device=device,
        seed=seed,
        critic_layers=int(config.get("critic_layers", 2)),
    )


def train_shared_step(policy: TorchSharedGRUPolicy, batch: list[Transition]) -> float:
    stats = policy.update(batch)
    return stats["policy_loss"] + stats["value_loss"]
