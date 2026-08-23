"""Population league: heuristic bots + frozen policy checkpoints."""

from __future__ import annotations

from typing import Any, Callable

from agents.heuristic.bots import get_bot
from engine.phases import random_choice_policy, random_play_policy
from engine.rng import GameRNG
from engine.state import GameState
from training.checkpoints import CheckpointManager, PolicyCheckpoint
from training.ctde_policy import SharedGRUPolicy

NegotiationFn = Callable[[GameState, int, GameRNG], None]
PlayFn = Callable[[GameState, int, list[dict]], list[int]]
ChoiceFn = Callable[[GameState, int, list[dict]], str]


class LeaguePool:
    """Mix heuristic bots and frozen checkpoints for opponent seats."""

    def __init__(self, config: dict[str, Any], checkpoint_mgr: CheckpointManager | None = None):
        self.config = config
        self.heuristic_names = list(
            config.get("league_bots", ["hoard", "aggressive", "ally_neighbor", "exploit"])
        )
        self.checkpoint_mgr = checkpoint_mgr
        self.checkpoint_mix = float(config.get("checkpoint_mix", 0.35))
        self._rng = None

    def set_seed(self, seed: int) -> None:
        import numpy as np

        self._rng = np.random.default_rng(seed)

    def resolve_bot_name(self, seat: int, game_index: int) -> str:
        names = self.heuristic_names
        if not names:
            return "random"
        offset = game_index % len(names)
        return names[(seat + offset) % len(names)]

    def should_use_checkpoint(self, game_index: int) -> bool:
        if not self.checkpoint_mgr or not self.checkpoint_mgr.list_checkpoints():
            return False
        r = float(self._rng.random()) if self._rng is not None else 0.5
        return r < self.checkpoint_mix

    def pick_checkpoint(self, game_index: int) -> PolicyCheckpoint | None:
        if not self.checkpoint_mgr:
            return None
        cps = self.checkpoint_mgr.list_checkpoints()
        if not cps:
            return None
        idx = game_index % len(cps)
        return cps[idx]

    def bot_fns_for_seat(self, seat: int, game_index: int) -> tuple[NegotiationFn, PlayFn, ChoiceFn]:
        name = self.resolve_bot_name(seat, game_index)
        return get_bot(name)

    def make_policy_opponent_fns(
        self, policy: SharedGRUPolicy, seat: int
    ) -> tuple[NegotiationFn, PlayFn, ChoiceFn]:
        from agents.heuristic.observation import actor_observation, global_observation

        policy.reset_hidden(seat)

        def negotiation(state: GameState, s: int, rng: GameRNG) -> None:
            if s != seat:
                return
            ao = actor_observation(state, s)
            go = global_observation(state, s)
            action, _, _ = policy.act_with_value(ao, go, s, deterministic=True)
            from training.episode_runner import apply_negotiation_action

            apply_negotiation_action(state, s, action, rng)

        def play(state: GameState, s: int, hand: list[dict]) -> list[int]:
            if s != seat:
                return random_play_policy(state, s, hand)
            ao = actor_observation(state, s)
            go = global_observation(state, s)
            action, _, _ = policy.act_with_value(ao, go, s, deterministic=True)
            n = 3 if s == state.king_seat else 2
            n = min(n, len(hand))
            indices = list(range(len(hand)))
            rng_local = GameRNG(seed=hash((s, state.current_round, action)) % (2**31))
            rng_local.shuffle(indices)
            return sorted(indices[:n])

        def choice(state: GameState, s: int, options: list[dict]) -> str:
            if s != seat:
                return random_choice_policy(state, s, options)
            ao = actor_observation(state, s)
            go = global_observation(state, s)
            action, _, _ = policy.act_with_value(ao, go, s, deterministic=True)
            return options[action % len(options)]["id"]

        return negotiation, play, choice
