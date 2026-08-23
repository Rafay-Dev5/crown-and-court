from __future__ import annotations

import argparse

import numpy as np

from agents.heuristic.observation import OBS_DIM
from agents.llm_negotiator import llm_negotiation_policy
from engine.cards import load_config
from engine.phases import random_choice_policy, random_play_policy, run_game
from engine.rng import GameRNG
from training.ppo import PPOConfig, SimplePolicy, train_step


def run_league(games: int = 100, seed: int = 0) -> dict:
    config = load_config("configs/balance.yaml")
    policy = SimplePolicy(seed=seed)
    cfg = PPOConfig()
    wins = 0
    for i in range(games):
        rng = GameRNG(seed=seed + i)
        state = run_game(
            config,
            rng,
            negotiation_policy=llm_negotiation_policy if config.get("playtest_mode") else None,
            play_policy=random_play_policy,
            choice_policy=random_choice_policy,
        )
        winner = state.seats[state.king_seat].person_id
        if winner == 0:
            wins += 1
        train_step(policy, np.zeros(OBS_DIM), 0, 1.0 if winner == 0 else 0.0, cfg)
    return {"games": games, "seat_0_win_rate": wins / games}


def main() -> None:
    parser = argparse.ArgumentParser(description="League training stub")
    parser.add_argument("--games", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    result = run_league(args.games, args.seed)
    print(f"League run: {result}")


if __name__ == "__main__":
    main()
