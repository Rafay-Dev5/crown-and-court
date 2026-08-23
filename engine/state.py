from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    KING = "king"
    NOBLE = "noble"


class Phase(str, Enum):
    SETUP = "setup"
    NEGOTIATION = "negotiation"
    PLAYING = "playing"
    SUCCESSION = "succession"
    GAME_END = "game_end"


@dataclass
class StatusTag:
    name: str
    expires_after_round: int


@dataclass
class ActiveShield:
    seat: int
    card_id: str
    blocks: str  # gold_theft | discard | steal_card | generic
    amount: int = 0
    targeted_attacker: int | None = None
    specificity: str = "generic"  # generic | targeted
    single_use: bool = True
    expires_after_round: int = 0
    consumed: bool = False


@dataclass
class PhaseAttack:
    attacker_seat: int
    target_seat: int
    attack_type: str
    amount: int = 0
    blocked: bool = False


@dataclass
class ChoiceRecord:
    round: int
    phase: str
    card_id: str
    choice_id: str
    seat: int


@dataclass
class DiceRecord:
    round: int
    phase: str
    card_id: str
    seat: int
    sides: int
    roll: int
    target_min: int
    success: bool


@dataclass
class Alliance:
    members: frozenset[int]
    declared_round: int
    terms: str = ""


@dataclass
class ConditionalPromise:
    id: str
    proposer: int
    target: int
    offer: dict[str, Any]
    condition: dict[str, Any]
    declared_round: int
    status: str = "pending"


@dataclass
class PlayerState:
    person_id: int
    gold: int = 0
    earned_gold: int = 0
    gifted_gold: int = 0
    legitimacy: int = 0


@dataclass
class SeatState:
    seat_id: int
    role: Role
    deck: list[dict[str, Any]] = field(default_factory=list)
    hand: list[dict[str, Any]] = field(default_factory=list)
    discard: list[dict[str, Any]] = field(default_factory=list)
    person_id: int = 0
    statuses: list[StatusTag] = field(default_factory=list)


@dataclass
class PendingChoice:
    seat: int
    card_id: str
    options: list[dict[str, str]]
    callback_key: str = ""


@dataclass
class PendingProtectionBet:
    seat: int
    card_id: str
    card: dict[str, Any]
    trigger: dict[str, Any]
    target_seat: int


@dataclass
class GameState:
    num_players: int
    n_rounds: int
    current_round: int = 0
    phase: Phase = Phase.SETUP
    king_seat: int = 0
    turn_direction: int = 1
    players: list[PlayerState] = field(default_factory=list)
    seats: list[SeatState] = field(default_factory=list)
    alliances: list[Alliance] = field(default_factory=list)
    conditional_promises: list[ConditionalPromise] = field(default_factory=list)
    active_shields: list[ActiveShield] = field(default_factory=list)
    phase_attacks: list[PhaseAttack] = field(default_factory=list)
    choice_log: list[ChoiceRecord] = field(default_factory=list)
    dice_log: list[DiceRecord] = field(default_factory=list)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    pending_choice: PendingChoice | None = None
    negotiation_history: list[dict[str, Any]] = field(default_factory=list)
    pending_proposals: list[dict[str, Any]] = field(default_factory=list)
    proposal_counter: int = 0
    card_set_version: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    system_gold: int = 0
    pending_protection_bets: list[PendingProtectionBet] = field(default_factory=list)
    negotiation_gift_sent: dict[int, int] = field(default_factory=dict)
    negotiation_trades_executed: dict[int, int] = field(default_factory=dict)

    def log_event(self, event_type: str, **payload: Any) -> None:
        self.event_log.append(
            {
                "type": event_type,
                "round": self.current_round,
                "phase": self.phase.value,
                **payload,
            }
        )

    def total_gold(self) -> int:
        return sum(p.gold for p in self.players) + self.system_gold

    def person_at_seat(self, seat: int) -> PlayerState:
        return self.players[self.seats[seat].person_id]

    def king_gold(self) -> int:
        return self.person_at_seat(self.king_seat).gold

    def king_earned_gold(self) -> int:
        return self.person_at_seat(self.king_seat).earned_gold

    def noble_seats(self) -> list[int]:
        return [i for i, s in enumerate(self.seats) if s.role == Role.NOBLE]

    def seat_order_from_king(self) -> list[int]:
        order: list[int] = []
        idx = self.king_seat
        for _ in range(self.num_players):
            order.append(idx)
            idx = (idx + self.turn_direction) % self.num_players
        return order

    def noble_play_order(self) -> list[int]:
        return [s for s in self.seat_order_from_king()[1:] if self.seats[s].role == Role.NOBLE]

    def has_alliance_between(self, a: int, b: int) -> bool:
        pair = frozenset({a, b})
        return any(alliance.members == pair for alliance in self.alliances)

    def has_status(self, seat: int, status_name: str) -> bool:
        return any(s.name == status_name for s in self.seats[seat].statuses)

    def was_attacked_this_phase(self, seat: int, attack_type: str | None = None) -> bool:
        for atk in self.phase_attacks:
            if atk.target_seat == seat and not atk.blocked:
                if attack_type is None or atk.attack_type == attack_type:
                    return True
        return False

    def prior_choice_within(self, seat: int, choice_id: str, within_rounds: int) -> bool:
        min_round = max(1, self.current_round - within_rounds + 1)
        return any(
            r.seat == seat
            and r.choice_id == choice_id
            and r.round >= min_round
            for r in self.choice_log
        )

    def failed_dice_for_card(self, seat: int, card_id: str, within_rounds: int = 2) -> bool:
        min_round = max(1, self.current_round - within_rounds + 1)
        return any(
            r.seat == seat
            and r.card_id == card_id
            and not r.success
            and r.round >= min_round
            for r in self.dice_log
        )

    def tick_statuses(self) -> None:
        for seat in self.seats:
            seat.statuses = [
                s for s in seat.statuses if s.expires_after_round > self.current_round
            ]
        self.active_shields = [
            s
            for s in self.active_shields
            if s.expires_after_round > self.current_round and not s.consumed
        ]
