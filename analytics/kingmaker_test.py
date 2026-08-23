from __future__ import annotations

import argparse
import json
from pathlib import Path

from analytics.stats import wilson_interval
from engine.cards import load_config
from engine.phases import setup_game
from engine.rng import GameRNG
from engine.succession import perform_seat_swap, resolve_succession


def run_kingmaker_scenario(games: int = 100, seed: int = 0, ledger: bool = True) -> dict:
    """Synthetic last-place gift scenario — measures gift-driven ascension rate."""
    config = load_config("configs/balance.yaml")
    config["n_rounds"] = 3
    config["num_players"] = 4
    checker = "earned_gold" if ledger else "gold_only"
    ascensions = 0
    gift_wins = 0

    for i in range(games):
        rng = GameRNG(seed=seed + i)
        state = setup_game(config, rng)
        state.current_round = config["n_rounds"]
        last_noble = state.noble_seats()[-1]
        recipient = state.noble_seats()[0]
        state.person_at_seat(last_noble).gold = 50
        state.person_at_seat(recipient).gold = 900
        state.person_at_seat(state.king_seat).gold = 1000
        state.person_at_seat(recipient).earned_gold = 600
        state.person_at_seat(last_noble).earned_gold = 50
        state.person_at_seat(state.king_seat).earned_gold = 1000

        gift = 2000
        state.person_at_seat(last_noble).gold -= min(gift, state.person_at_seat(last_noble).gold)
        state.person_at_seat(recipient).gold += gift
        if ledger:
            state.person_at_seat(recipient).gifted_gold += gift
        else:
            state.person_at_seat(recipient).earned_gold += gift
        state.log_event("gold_gifted", from_seat=last_noble, to_seat=recipient, amount=gift)

        ascending = resolve_succession(state, checker)
        if ascending is not None:
            ascensions += 1
            perform_seat_swap(state, ascending)
            if ascending == recipient:
                gift_wins += 1
        state.log_event("game_end", winner_seat=state.king_seat)
        _ = state.event_log

    ascension_rate = ascensions / games if games else 0.0
    gift_ascension_rate = gift_wins / games if games else 0.0
    lo, hi = wilson_interval(ascensions, games)
    return {
        "ledger_enabled": ledger,
        "checker": checker,
        "games": games,
        "ascension_rate": ascension_rate,
        "gift_recipient_ascension_rate": gift_ascension_rate,
        "assisted_win_rate": gift_ascension_rate,
        "ci_low": lo,
        "ci_high": hi,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Kingmaker validation A/B")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="game_logs/kingmaker_ab.json")
    args = parser.parse_args()

    off = run_kingmaker_scenario(args.games, args.seed, ledger=False)
    on = run_kingmaker_scenario(args.games, args.seed + 10000, ledger=True)
    result = {
        "gold_only": off,
        "earned_gold_ledger": on,
        "fix_reduces_assisted_wins": on["gift_recipient_ascension_rate"] < off["gift_recipient_ascension_rate"],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
