from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.state import GameState, Role


TOTAL_MATCHES = 4
WIN_POINTS_THRESHOLD = 10


@dataclass
class PlayerMeta:
    player_id: str
    seat: int
    total_points: int = 0
    king_finish_wins: int = 0
    noble_points_earned: int = 0
    starting_king_matches: list[int] = field(default_factory=list)


@dataclass
class MatchResult:
    match_number: int
    winner_seat: int
    winner_player_id: str
    winner_started_as_king: bool
    points_awarded: dict[str, int]
    placements: list[dict[str, Any]]


class MetaGameManager:
    """Tracks 4-match meta-game: King rotation, scoring, tie-breakers."""

    def __init__(self, player_ids: list[str], player_names: list[str]):
        if len(player_ids) != 4:
            raise ValueError("Meta-game requires exactly 4 players")
        self.player_ids = player_ids
        self.player_names = player_names
        self.players: dict[str, PlayerMeta] = {
            pid: PlayerMeta(player_id=pid, seat=i) for i, pid in enumerate(player_ids)
        }
        self.current_match = 0
        self.match_results: list[MatchResult] = []
        self.starting_king_seats: list[int] = []
        self._starting_roles: dict[int, dict[int, Role]] = {}

    def starting_king_seat_for_match(self, match_num: int) -> int:
        """Rotate starting King: match 1 -> seat 0, match 2 -> seat 1, etc."""
        return (match_num - 1) % 4

    def record_match_start(self, match_num: int, state: GameState) -> None:
        self.current_match = match_num
        king_seat = state.king_seat
        self.starting_king_seats.append(king_seat)
        roles: dict[int, Role] = {}
        for seat in range(state.num_players):
            roles[seat] = state.seats[seat].role
            pid = self._player_id_for_seat(seat)
            if state.seats[seat].role == Role.KING:
                self.players[pid].starting_king_matches.append(match_num)
        self._starting_roles[match_num] = roles

    def _player_id_for_seat(self, seat: int) -> str:
        return self.player_ids[seat]

    def _seat_for_player(self, player_id: str) -> int:
        return self.player_ids.index(player_id)

    def compute_match_scores(self, state: GameState) -> MatchResult:
        match_num = self.current_match
        starting_roles = self._starting_roles.get(match_num, {})
        winner_seat = state.king_seat
        winner_pid = self._player_id_for_seat(winner_seat)
        winner_started_as_king = starting_roles.get(winner_seat) == Role.KING

        points: dict[str, int] = {pid: 0 for pid in self.player_ids}

        if winner_started_as_king:
            points[winner_pid] = 4
            self.players[winner_pid].king_finish_wins += 1
        else:
            points[winner_pid] = 5
            self.players[winner_pid].noble_points_earned += 5

        noble_starter_seats = [
            s for s, r in starting_roles.items() if r == Role.NOBLE
        ]
        non_winner_nobles = [s for s in noble_starter_seats if s != winner_seat]

        king_starter_seat = next(
            (s for s, r in starting_roles.items() if r == Role.KING), None
        )
        if king_starter_seat is not None and king_starter_seat != winner_seat:
            king_pid = self._player_id_for_seat(king_starter_seat)
            points[king_pid] = 0

        ranked = self._rank_nobles_by_earned_gold(state, non_winner_nobles)
        if winner_started_as_king:
            placement_points = [3, 2, 1]
        else:
            placement_points = [3, 2]

        for i, seat in enumerate(ranked):
            if i < len(placement_points):
                pid = self._player_id_for_seat(seat)
                pts = placement_points[i]
                points[pid] += pts
                self.players[pid].noble_points_earned += pts

        placements = []
        for seat in range(state.num_players):
            pid = self._player_id_for_seat(seat)
            person = state.person_at_seat(seat)
            placements.append(
                {
                    "seat": seat,
                    "player_id": pid,
                    "player_name": self.player_names[seat],
                    "earned_gold": person.earned_gold,
                    "started_as_king": starting_roles.get(seat) == Role.KING,
                    "is_winner": seat == winner_seat,
                    "points_earned": points[pid],
                }
            )
        placements.sort(key=lambda p: -p["points_earned"])

        for pid, pts in points.items():
            self.players[pid].total_points += pts

        result = MatchResult(
            match_number=match_num,
            winner_seat=winner_seat,
            winner_player_id=winner_pid,
            winner_started_as_king=winner_started_as_king,
            points_awarded=points,
            placements=placements,
        )
        self.match_results.append(result)
        return result

    def _rank_nobles_by_earned_gold(
        self, state: GameState, seats: list[int]
    ) -> list[int]:
        def sort_key(seat: int) -> tuple[int, int]:
            person = state.person_at_seat(seat)
            noble_order = state.noble_play_order()
            order_idx = noble_order.index(seat) if seat in noble_order else 999
            return (-person.earned_gold, order_idx)

        return sorted(seats, key=sort_key)

    def is_game_over(self) -> bool:
        if any(p.total_points >= WIN_POINTS_THRESHOLD for p in self.players.values()):
            return True
        return len(self.match_results) >= TOTAL_MATCHES

    def determine_winners(self) -> list[str]:
        if not self.is_game_over():
            return []

        ranked = sorted(
            self.player_ids,
            key=lambda pid: (
                -self.players[pid].total_points,
                -self.players[pid].king_finish_wins,
                -self.players[pid].noble_points_earned,
            ),
        )
        top = self.players[ranked[0]]
        winners = [ranked[0]]
        for pid in ranked[1:]:
            p = self.players[pid]
            if (
                p.total_points == top.total_points
                and p.king_finish_wins == top.king_finish_wins
                and p.noble_points_earned == top.noble_points_earned
            ):
                winners.append(pid)
            else:
                break
        return winners

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_match": self.current_match,
            "total_matches": TOTAL_MATCHES,
            "total_points": {pid: p.total_points for pid, p in self.players.items()},
            "king_finish_wins": {
                pid: p.king_finish_wins for pid, p in self.players.items()
            },
            "noble_points_earned": {
                pid: p.noble_points_earned for pid, p in self.players.items()
            },
            "player_names": dict(zip(self.player_ids, self.player_names)),
            "match_results": [
                {
                    "match_number": r.match_number,
                    "winner_player_id": r.winner_player_id,
                    "winner_started_as_king": r.winner_started_as_king,
                    "points_awarded": r.points_awarded,
                    "placements": r.placements,
                }
                for r in self.match_results
            ],
        }
