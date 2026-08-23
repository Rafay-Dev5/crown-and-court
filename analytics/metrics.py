from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from analytics.diagnostics import run_diagnostics
from analytics.stats import wilson_interval


METRIC_EXPLANATIONS: dict[str, str] = {
    "seat_position_win_rate": "How often each starting seat wins. Uneven rates may mean a seating bug.",
    "role_win_rate": "Win rate for players who started as King vs Noble. Shows if starting role is unfair.",
    "card_pick_rate": "How often a card gets played when it could be. Low = dead card; very high = auto-include.",
    "card_win_contribution": "Win rate in games where this card was played, vs overall. High = possible overperformer.",
    "card_win_contribution_by_role": (
        "Win rate split by whether the player was King or Noble when the card was played. "
        "Use this before nerfing — raw contribution confounds role with card power."
    ),
    "assisted_win_rate": (
        "Games where the winner's person received negotiation gold_gifted events "
        "(to_person == winner_person)."
    ),
    "assisted_win_rate_seat": "Legacy seat-based assisted metric (to_seat == winner_seat).",
    "assisted_win_modes": "Why assisted wins happened (stacking, starting king gifts, etc.).",
    "shield_hit_rate": "Protection trigger resolved as a correct guess at end of playing phase.",
    "shield_block_rate": "Active shields that actually blocked an attack (shield_blocked events).",
    "whiff_penalty_rate": "Protection guesses that whiffed and triggered on_whiff_penalty.",
    "protection_net_ev": "Average gold swing per protection card play (hits and whiffs combined).",
    "skill_gap": "How much trained bots beat random bots. Too low = no skill; too high = no room for luck.",
    "exploitability": "How much a sharp counter-strategy beats your policy. Lower means harder to exploit.",
    "promise_keep_rate": "Alliances and conditional promises kept vs broken. Tests negotiation meaning.",
}

SEAT_LABELS: dict[int, str] = {
    0: "Seat 0",
    1: "Seat 1",
    2: "Seat 2",
    3: "Seat 3",
    4: "Seat 4",
    5: "Seat 5",
    6: "Seat 6",
    7: "Seat 7",
}


def _role_at_seat(king_seat: int, seat: int | None) -> str | None:
    if seat is None:
        return None
    return "king" if int(seat) == king_seat else "noble"


def _contrib_bucket(
    games: int, wins: int, baseline: float
) -> dict[str, float | int]:
    rate = wins / games if games else 0.0
    return {
        "games_with_card": games,
        "wins_when_played": wins,
        "win_rate_when_played": rate,
        "delta_vs_fair": rate - baseline,
    }


def compute_metrics(game_logs: list[list[dict[str, Any]]]) -> dict[str, Any]:
    wins_by_seat: Counter = Counter()
    wins_with_card: Counter = Counter()
    games_with_card: Counter = Counter()
    card_plays: Counter = Counter()
    role_games: Counter = Counter()
    role_wins: Counter = Counter()
    assisted_wins = 0
    assisted_wins_seat = 0
    shield_hits = 0
    shield_whiffs = 0
    shield_blocks = 0
    starting_king_wins = 0
    starting_noble_wins = 0
    succession_games = 0
    succession_events = 0
    succession_by_round: Counter = Counter()
    protection_gold_delta: dict[str, list[int]] = defaultdict(list)
    total_games = len(game_logs)

    for log in game_logs:
        winner_seat = None
        winner_person = None
        starting_king_person: int | None = None
        king_seat = 0
        gifted_to_winner = False
        gifted_to_winner_person = False
        gift_events: list[dict[str, Any]] = []
        card_players: dict[str, set[int]] = defaultdict(set)
        card_role_seats: dict[tuple[str, str], set[int]] = defaultdict(set)
        game_succession = 0
        prev_king = king_seat

        for event in log:
            if event["type"] == "game_setup":
                skp = event.get("starting_king_person")
                if skp is not None:
                    starting_king_person = int(skp)
                sks = event.get("starting_king_seat")
                if sks is not None:
                    king_seat = int(sks)
            if event["type"] == "succession":
                new_k = int(event.get("new_king_seat", king_seat))
                if new_k != prev_king:
                    game_succession += 1
                    succession_by_round[int(event.get("round", 0))] += 1
                king_seat = new_k
                prev_king = new_k
            if event["type"] == "game_end":
                winner_seat = event.get("winner_seat")
                winner_person = event.get("winner_person")
            if event["type"] == "gold_gifted":
                gift_events.append(event)
            if event["type"] == "card_revealed":
                cid = event.get("card_id")
                seat = event.get("seat")
                if cid:
                    card_plays[cid] += 1
                    if seat is not None:
                        seat_i = int(seat)
                        card_players[cid].add(seat_i)
                        role = _role_at_seat(king_seat, seat_i)
                        if role:
                            card_role_seats[(cid, role)].add(seat_i)

        if winner_seat is not None:
            for gift in gift_events:
                if gift.get("to_seat") == winner_seat:
                    gifted_to_winner = True
                if winner_person is not None and gift.get("to_person") == winner_person:
                    gifted_to_winner_person = True
                if gifted_to_winner and gifted_to_winner_person:
                    break
            wins_by_seat[winner_seat] += 1
            for cid, seats in card_players.items():
                games_with_card[cid] += 1
                if winner_seat in seats:
                    wins_with_card[cid] += 1
            for (cid, role), seats in card_role_seats.items():
                role_games[(cid, role)] += 1
                if int(winner_seat) in seats:
                    role_wins[(cid, role)] += 1

        if winner_person is not None:
            skp = starting_king_person if starting_king_person is not None else 0
            if int(winner_person) == skp:
                starting_king_wins += 1
            else:
                starting_noble_wins += 1

        for event in log:
            if event["type"] == "protection_hit":
                shield_hits += 1
                cid = event.get("card_id")
                if cid:
                    protection_gold_delta[cid].append(50)
            if event["type"] == "protection_whiff":
                shield_whiffs += 1
                cid = event.get("card_id")
                if cid:
                    protection_gold_delta[cid].append(-25)
            if event["type"] == "shield_blocked":
                shield_blocks += 1

        if gifted_to_winner_person:
            assisted_wins += 1
        if gifted_to_winner:
            assisted_wins_seat += 1

        if game_succession > 0:
            succession_games += 1
        succession_events += game_succession

    win_rates = {str(k): v / total_games for k, v in wins_by_seat.items()} if total_games else {}
    assisted_rate = assisted_wins / total_games if total_games else 0.0
    assisted_rate_seat = assisted_wins_seat / total_games if total_games else 0.0
    lo, hi = wilson_interval(assisted_wins, total_games)
    baseline_win_rate = 1.0 / max(1, len(win_rates) or 6)

    card_win_contribution: dict[str, dict[str, float]] = {}
    for cid, games in games_with_card.items():
        wins = wins_with_card.get(cid, 0)
        card_win_contribution[cid] = _contrib_bucket(games, wins, baseline_win_rate)

    card_win_contribution_by_role: dict[str, dict[str, dict[str, float | int]]] = defaultdict(dict)
    for (cid, role), games in role_games.items():
        wins = role_wins.get((cid, role), 0)
        card_win_contribution_by_role[cid][role] = _contrib_bucket(games, wins, baseline_win_rate)
    card_win_contribution_by_role = dict(card_win_contribution_by_role)

    card_pick_rate = {
        cid: count / total_games if total_games else 0.0
        for cid, count in card_plays.items()
    }

    protection_ev = {
        cid: sum(deltas) / len(deltas) if deltas else 0.0
        for cid, deltas in protection_gold_delta.items()
    }
    shield_total = shield_hits + shield_whiffs
    diagnostics = run_diagnostics(game_logs)

    return {
        "total_games": total_games,
        "win_rates_by_seat": win_rates,
        "role_win_rate": {
            "started_as_king": starting_king_wins / total_games if total_games else 0.0,
            "started_as_noble": starting_noble_wins / total_games if total_games else 0.0,
        },
        "assisted_win_rate": assisted_rate,
        "assisted_win_rate_seat": assisted_rate_seat,
        "assisted_win_rate_ci": {"low": lo, "high": hi},
        "assisted_win_modes": diagnostics.get("assisted_win_modes", {}),
        "shield_hit_rate": shield_hits / shield_total if shield_total else 0.0,
        "shield_block_rate": shield_blocks / shield_total if shield_total else 0.0,
        "shield_block_count": shield_blocks,
        "whiff_penalty_rate": shield_whiffs / shield_total if shield_total else 0.0,
        "protection_net_ev": protection_ev,
        "card_pick_counts": dict(card_plays),
        "card_pick_rate": card_pick_rate,
        "card_win_contribution": card_win_contribution,
        "card_win_contribution_by_role": card_win_contribution_by_role,
        "succession_count_per_game": succession_events / total_games if total_games else 0.0,
        "games_with_succession": succession_games,
        "succession_rate": succession_games / total_games if total_games else 0.0,
        "succession_by_round": dict(sorted(succession_by_round.items())),
        "diagnostics": diagnostics,
        "explanations": METRIC_EXPLANATIONS,
    }
