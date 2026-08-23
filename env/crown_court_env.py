from __future__ import annotations

from typing import Any

import numpy as np
from gymnasium import spaces
from pettingzoo.utils.env import AECEnv

from agents.heuristic.observation import OBS_DIM, seat_observation
from engine.cards import load_config
from engine.decisions import DecisionEngine, DecisionType
from engine.negotiation import pass_action, propose_trade
from engine.rng import GameRNG


def _apply_negotiation_action(state, seat: int, action: int, rng: GameRNG) -> None:
    others = [s for s in range(state.num_players) if s != seat]
    if action == 0 or not others:
        pass_action(state, seat)
    elif action == 1:
        target = others[action % len(others)]
        propose_trade(state, seat, target, {"gold": 50}, {"gold": 0})
    else:
        pass_action(state, seat)


class CrownCourtEnv(AECEnv):
    metadata = {"render_modes": ["human"], "name": "crown_court_v0"}

    def __init__(self, config: dict[str, Any] | None = None, seed: int = 0):
        super().__init__()
        self.config = load_config() if config is None else {**load_config(), **config}
        self.seed_val = seed
        self.engine: DecisionEngine | None = None
        self._rng = GameRNG(seed=seed)
        num = int(self.config.get("num_players", 6))
        self.possible_agents = [f"player_{i}" for i in range(num)]
        self.agents = self.possible_agents[:]
        self.action_spaces = {a: spaces.Discrete(64) for a in self.possible_agents}
        self.observation_spaces = {
            a: spaces.Box(low=0, high=1, shape=(OBS_DIM,), dtype=np.float32) for a in self.possible_agents
        }

    def reset(self, seed: int | None = None, options: dict | None = None):
        if seed is not None:
            self.seed_val = seed
        self._rng = GameRNG(seed=self.seed_val)
        self.engine = DecisionEngine(self.config, self._rng)
        self.engine.reset()
        self.agents = self.possible_agents[:]
        self.rewards = {a: 0.0 for a in self.agents}
        self._cumulative_rewards = {a: 0.0 for a in self.agents}
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}
        self._sync_agent_selection()
        obs = self.observe(self.agent_selection) if self.agent_selection else {}
        return obs, self.infos

    def _sync_agent_selection(self) -> None:
        if not self.engine or self.engine.done:
            self.agents = []
            return
        dec = self.engine.current_decision()
        if dec:
            self.agent_selection = f"player_{dec.seat}"
        else:
            self.engine.step(0)
            self._sync_agent_selection()

    def observe(self, agent: str):
        if not self.engine or not self.engine.state:
            return np.zeros(OBS_DIM, dtype=np.float32)
        seat = int(agent.split("_")[1])
        return seat_observation(self.engine.state, seat)

    def step(self, action: int):
        if not self.engine or not self.agents:
            return
        agent = self.agent_selection
        if self.terminations.get(agent) or self.truncations.get(agent):
            return self._was_dead_step(action)

        dec = self.engine.current_decision()
        if dec and dec.dtype == DecisionType.NEGOTIATION:
            self.engine.step(action, _apply_negotiation_action)
        else:
            self.engine.step(action)

        if self.engine.done:
            winner = self.engine.state.king_seat
            for a in self.possible_agents:
                seat = int(a.split("_")[1])
                person = self.engine.state.seats[seat].person_id
                win_person = self.engine.state.seats[winner].person_id
                self.rewards[a] = 1.0 if person == win_person else 0.0
                self.terminations[a] = True
            self.agents = []
        else:
            self._sync_agent_selection()

    def render(self):
        if self.engine and self.engine.state:
            s = self.engine.state
            print(f"R{s.current_round} phase={s.phase.value} king_seat={s.king_seat}")

    def close(self):
        pass
