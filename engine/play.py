from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.cards import load_config
from engine.phases import (
    random_choice_policy,
    random_negotiation_policy,
    random_play_policy,
    run_game,
)
from engine.rng import GameRNG


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Crown & Court simulation game")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--players", type=int, default=6)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--log", type=str, default=None)
    parser.add_argument("--playtest", action="store_true", help="Enable playtest mode flags")
    args = parser.parse_args()

    config = load_config(args.config)
    config["num_players"] = args.players
    config["n_rounds"] = args.rounds
    if args.playtest:
        config["playtest_mode"] = True

    rng = GameRNG(seed=args.seed)
    state = run_game(
        config,
        rng,
        negotiation_policy=random_negotiation_policy,
        play_policy=random_play_policy,
        choice_policy=random_choice_policy,
    )

    winner = state.seats[state.king_seat].person_id
    print(f"Game complete. Winner person_id={winner} (King seat {state.king_seat})")
    print(f"Rounds played: {state.n_rounds}, events: {len(state.event_log)}")

    if args.log:
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as f:
            for event in state.event_log:
                f.write(json.dumps(event) + "\n")
        print(f"Log written to {log_path}")


if __name__ == "__main__":
    main()
