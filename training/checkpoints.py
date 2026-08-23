"""Save/load frozen policy checkpoints for population league play."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from training.ctde_policy import SharedGRUPolicy


@dataclass
class PolicyCheckpoint:
    episode: int
    path: Path
    policy: SharedGRUPolicy

    @property
    def label(self) -> str:
        return f"checkpoint_ep{self.episode}"


class CheckpointManager:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    from training.ctde_policy import SharedGRUPolicy
    from training.ctde_policy_torch import TorchSharedGRUPolicy

    def save(self, policy: SharedGRUPolicy | TorchSharedGRUPolicy, episode: int) -> PolicyCheckpoint:
        path = self.root / f"policy_ep{episode:06d}.json"
        policy.save(path)
        entries = self._load_index()
        entries.append({"episode": episode, "path": str(path)})
        self.index_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        clone = policy.clone_frozen() if hasattr(policy, "clone_frozen") else policy
        if hasattr(clone, "to_numpy_policy"):
            clone = clone.to_numpy_policy()
        return PolicyCheckpoint(episode=episode, path=path, policy=clone)

    def list_checkpoints(self) -> list[PolicyCheckpoint]:
        from training.policy_factory import load_policy

        entries = self._load_index()
        out: list[PolicyCheckpoint] = []
        for e in entries:
            path = Path(e["path"])
            if path.exists():
                policy = load_policy(path)
                if hasattr(policy, "to_numpy_policy"):
                    policy = policy.to_numpy_policy()
                out.append(
                    PolicyCheckpoint(
                        episode=int(e["episode"]),
                        path=path,
                        policy=policy,
                    )
                )
        return out

    def latest(self) -> PolicyCheckpoint | None:
        cps = self.list_checkpoints()
        return cps[-1] if cps else None

    def _load_index(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))
