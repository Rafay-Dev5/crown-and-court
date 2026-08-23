from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClientMessageType(str, Enum):
    JOIN = "join"
    RECONNECT = "reconnect"
    READY = "ready"
    START = "start"
    BEGIN_MATCH = "begin_match"
    NEXT_MATCH = "next_match"
    ACTION = "action"
    ACCEPT_PROPOSAL = "accept_proposal"
    REJECT_PROPOSAL = "reject_proposal"
    ADD_BOTS = "add_bots"


class ServerMessageType(str, Enum):
    ERROR = "error"
    LOBBY_STATE = "lobby_state"
    MATCH_INTRO = "match_intro"
    GAME_STATE = "game_state"
    DECISION_REQUIRED = "decision_required"
    EVENT = "event"
    PROPOSAL_RECEIVED = "proposal_received"
    MATCH_END = "match_end"
    GAME_END = "game_end"


class ClientMessage(BaseModel):
    type: ClientMessageType
    payload: dict[str, Any] = Field(default_factory=dict)


class PlayerInfo(BaseModel):
    id: str
    name: str
    seat: int | None = None
    ready: bool = False
    connected: bool = True
    is_bot: bool = False


class MetaScores(BaseModel):
    total_points: dict[str, int] = Field(default_factory=dict)
    king_finish_wins: dict[str, int] = Field(default_factory=dict)
    noble_points_earned: dict[str, int] = Field(default_factory=dict)
    current_match: int = 0
    total_matches: int = 4


class PublicStatus(BaseModel):
    name: str
    remaining_rounds: int


class PublicSeatState(BaseModel):
    seat_id: int
    person_id: int
    role: str
    player_id: str
    player_name: str
    gold: int
    earned_gold: int
    gifted_gold: int
    gift_sent: int = 0
    cards_sent: int = 0
    hand_size: int
    deck_size: int
    statuses: list[PublicStatus] = Field(default_factory=list)


class PublicGameState(BaseModel):
    current_round: int
    n_rounds: int
    phase: str
    king_seat: int
    turn_direction: int
    seats: list[PublicSeatState]
    alliances: list[list[int]]
    event_log_tail: list[dict[str, Any]]
    pending_proposals: list[dict[str, Any]]
    negotiation_tick: int | None = None
    negotiation_ticks: int | None = None
    locked_seats: list[int] = Field(default_factory=list)
    max_negotiation_gift: int = 120
    max_negotiation_gift_per_phase: int = 120


class PrivateGameState(BaseModel):
    hand: list[dict[str, Any]]
    seat: int
    person_id: int
    peek: dict[str, Any] | None = None
    discard_choice: dict[str, Any] | None = None


class DecisionInfo(BaseModel):
    decision_id: str
    seat: int
    dtype: str
    context: dict[str, Any] = Field(default_factory=dict)


class ServerMessage(BaseModel):
    type: ServerMessageType
    payload: dict[str, Any] = Field(default_factory=dict)

    def model_dump_json(self, **kwargs: Any) -> str:
        return super().model_dump_json(**kwargs)
