from __future__ import annotations

from typing import Callable, Protocol

from engine.state import GameState


class SuccessionChecker(Protocol):
    def __call__(self, state: GameState, seat: int) -> bool: ...


def gold_only_eligible(state: GameState, seat: int) -> bool:
    from engine.state import Role

    if state.seats[seat].role != Role.NOBLE:
        return False
    noble = state.person_at_seat(seat)
    king = state.person_at_seat(state.king_seat)
    return noble.gold > king.gold


def earned_gold_eligible(state: GameState, seat: int) -> bool:
    """Only earned gold counts toward succession (Card PRD §6)."""
    from engine.state import Role

    if state.seats[seat].role != Role.NOBLE:
        return False
    noble = state.person_at_seat(seat)
    king = state.person_at_seat(state.king_seat)
    return noble.earned_gold > king.earned_gold


def legitimacy_gated_eligible(state: GameState, seat: int) -> bool:
    from engine.state import Role

    if state.seats[seat].role != Role.NOBLE:
        return False
    noble = state.person_at_seat(seat)
    king = state.person_at_seat(state.king_seat)
    threshold = state.config.get("legitimacy_threshold", 0)
    round_threshold = state.config.get("legitimacy_threshold_by_round", {})
    if round_threshold:
        threshold = round_threshold.get(state.current_round, threshold)
    return noble.earned_gold > king.earned_gold and noble.legitimacy >= threshold


CHECKERS: dict[str, Callable[[GameState, int], bool]] = {
    "gold_only": gold_only_eligible,
    "earned_gold": earned_gold_eligible,
    "legitimacy": legitimacy_gated_eligible,
}


def get_checker(name: str) -> SuccessionChecker:
    return CHECKERS.get(name, earned_gold_eligible)


def find_succession_block(state: GameState) -> bool:
    """Return True if any active status blocks succession this check."""
    for seat_idx in range(state.num_players):
        if state.has_status(seat_idx, "block_succession"):
            return True
    return False


def resolve_succession(state: GameState, checker_name: str = "earned_gold") -> int | None:
    """Return ascending seat id or None. Respects block_succession status."""
    if find_succession_block(state):
        state.log_event("succession_blocked")
        return None

    checker = get_checker(checker_name)
    qualifiers = [s for s in state.noble_seats() if checker(state, s)]
    if not qualifiers:
        return None

    def sort_key(seat: int) -> tuple:
        noble = state.person_at_seat(seat)
        order = state.noble_play_order()
        turn_idx = order.index(seat) if seat in order else 999
        return (-noble.earned_gold, turn_idx)

    ascending = min(qualifiers, key=sort_key)
    return ascending


def perform_seat_swap(state: GameState, noble_seat: int) -> None:
    """Swap king and noble seats — decks/hands/discards move, gold stays with people."""
    king_seat = state.king_seat
    if noble_seat == king_seat:
        return

    king_chair = state.seats[king_seat]
    noble_chair = state.seats[noble_seat]

    king_chair.role, noble_chair.role = noble_chair.role, king_chair.role
    (
        king_chair.deck,
        noble_chair.deck,
        king_chair.hand,
        noble_chair.hand,
        king_chair.discard,
        noble_chair.discard,
    ) = (
        noble_chair.deck,
        king_chair.deck,
        noble_chair.hand,
        king_chair.hand,
        noble_chair.discard,
        king_chair.discard,
    )

    state.king_seat = noble_seat
    state.log_event(
        "succession",
        former_king_seat=king_seat,
        new_king_seat=noble_seat,
        new_king_person=noble_chair.person_id,
    )
