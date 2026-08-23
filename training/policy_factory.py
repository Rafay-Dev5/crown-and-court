"""Build / load CTDE policies (numpy or torch)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from training.ctde_policy import SharedGRUPolicy, build_shared_policy


def build_policy(config: dict[str, Any], seed: int = 0):
    backend = str(config.get("policy_backend", "numpy")).lower()
    if backend == "torch":
        from training.ctde_policy_torch import build_torch_policy

        return build_torch_policy(config, seed=seed)
    return build_shared_policy(config, seed=seed)


def load_policy(path: Path | str, config: dict[str, Any] | None = None, device: str | None = None):
    path = Path(path)
    meta = {}
    if path.exists():
        import json

        meta = json.loads(path.read_text(encoding="utf-8"))
    backend = meta.get("backend") or (config or {}).get("policy_backend", "numpy")
    if str(backend).lower() == "torch" or meta.get("weights_file"):
        from training.ctde_policy_torch import TorchSharedGRUPolicy, resolve_device

        return TorchSharedGRUPolicy.load(path, device=resolve_device(device or (config or {}).get("device")))
    return SharedGRUPolicy.load(path)
