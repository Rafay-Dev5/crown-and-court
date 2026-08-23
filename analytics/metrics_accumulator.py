"""Incremental signoff metrics without retaining full event logs."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


class SignoffMetricsAccumulator:
    """Accumulates balance gate metrics from per-game summaries."""

    def __init__(self) -> None:
        self.total_games = 0
        self.wins_by_seat: Counter = Counter()
        self.starting_king_wins = 0
        self.starting_noble_wins = 0
        self.assisted_wins = 0
        self.shield_hits = 0
        self.shield_whiffs = 0
        self.shield_blocks = 0
        self.succession_events = 0
        self.games_with_succession = 0
        self.succession_by_round: Counter = Counter()

    def add(self, summary: dict[str, Any]) -> None:
        self.total_games += 1
        ws = summary.get("winner_seat")
        if ws is not None:
            self.wins_by_seat[int(ws)] += 1
        if summary.get("assisted_win"):
            self.assisted_wins += 1
        self.shield_hits += int(summary.get("shield_hits", 0))
        self.shield_whiffs += int(summary.get("shield_whiffs", 0))
        self.shield_blocks += int(summary.get("shield_blocks", 0))
        if summary.get("starting_king_won"):
            self.starting_king_wins += 1
        else:
            self.starting_noble_wins += 1
        sc = int(summary.get("succession_count", 0))
        self.succession_events += sc
        if sc > 0:
            self.games_with_succession += 1
        for rnd, cnt in (summary.get("succession_by_round") or {}).items():
            self.succession_by_round[int(rnd)] += int(cnt)

    def to_metrics(self) -> dict[str, Any]:
        n = self.total_games or 1
        seat_rates = {str(k): v / n for k, v in sorted(self.wins_by_seat.items())}
        return {
            "assisted_win_rate": self.assisted_wins / n,
            "shield_hit_rate": self.shield_hits / max(1, self.shield_hits + self.shield_whiffs),
            "shield_block_rate": self.shield_blocks / n,
            "win_rates_by_seat": seat_rates,
            "role_win_rate": {
                "started_as_king": self.starting_king_wins / n,
                "started_as_noble": self.starting_noble_wins / n,
            },
            "succession_count_per_game": self.succession_events / n,
            "games_with_succession": self.games_with_succession,
            "succession_rate": self.games_with_succession / n,
            "succession_by_round": dict(sorted(self.succession_by_round.items())),
        }


def extract_game_summary(event_log: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact per-game stats for signoff gates."""
    winner_seat = None
    winner_person = None
    starting_king_person: int | None = None
    king_seat = 0
    gift_events: list[dict] = []
    shield_hits = shield_whiffs = shield_blocks = 0
    succession_count = 0
    succession_by_round: dict[int, int] = defaultdict(int)
    prev_king_seat = None

    for event in event_log:
        et = event.get("type")
        if et == "game_setup":
            skp = event.get("starting_king_person")
            if skp is not None:
                starting_king_person = int(skp)
            sks = event.get("starting_king_seat")
            if sks is not None:
                king_seat = int(sks)
                prev_king_seat = king_seat
        elif et == "succession":
            new_seat = int(event.get("new_king_seat", king_seat))
            if prev_king_seat is not None and new_seat != prev_king_seat:
                succession_count += 1
                rnd = int(event.get("round", 0))
                succession_by_round[rnd] += 1
            king_seat = new_seat
            prev_king_seat = king_seat
        elif et == "game_end":
            winner_seat = event.get("winner_seat")
            winner_person = event.get("winner_person")
        elif et == "gold_gifted":
            gift_events.append(event)
        elif et == "protection_hit":
            shield_hits += 1
        elif et == "protection_whiff":
            shield_whiffs += 1
        elif et == "shield_blocked":
            shield_blocks += 1

    assisted = False
    if winner_person is not None:
        assisted = any(g.get("to_person") == winner_person for g in gift_events)
    elif winner_seat is not None:
        assisted = any(g.get("to_seat") == winner_seat for g in gift_events)

    starting_king_won = (
        starting_king_person is not None
        and winner_person is not None
        and int(winner_person) == int(starting_king_person)
    )

    return {
        "winner_seat": winner_seat,
        "winner_person": winner_person,
        "assisted_win": assisted,
        "shield_hits": shield_hits,
        "shield_whiffs": shield_whiffs,
        "shield_blocks": shield_blocks,
        "starting_king_won": starting_king_won,
        "succession_count": succession_count,
        "succession_by_round": dict(succession_by_round),
    }
