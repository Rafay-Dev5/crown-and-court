from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import WebSocket

from web.server.game_session import GameSession, HumanAction
from web.server.meta_game import MetaGameManager, TOTAL_MATCHES
from web.server.protocol import PlayerInfo, ServerMessage, ServerMessageType


class RoomPhase(str, Enum):
    LOBBY = "lobby"
    MATCH_INTRO = "match_intro"
    PLAYING = "playing"
    MATCH_END = "match_end"
    GAME_END = "game_end"


MAX_PLAYERS = 4


def generate_room_code(length: int = 4) -> str:
    chars = string.ascii_uppercase + string.digits
    return "-".join(
        "".join(random.choices(chars, k=length))
        for _ in range(1)
    )[:9]


@dataclass
class ConnectedPlayer:
    id: str
    name: str
    websocket: WebSocket | None = None
    ready: bool = False
    reconnect_token: str = field(default_factory=lambda: str(uuid.uuid4()))
    seat: int | None = None


@dataclass
class GameRoom:
    code: str
    host_id: str
    players: dict[str, ConnectedPlayer] = field(default_factory=dict)
    phase: RoomPhase = RoomPhase.LOBBY
    meta: MetaGameManager | None = None
    session: GameSession | None = None
    pending_match: int = 0

    def player_list(self) -> list[PlayerInfo]:
        ordered = sorted(self.players.values(), key=lambda p: p.seat if p.seat is not None else 99)
        return [
            PlayerInfo(
                id=p.id,
                name=p.name,
                seat=p.seat,
                ready=p.ready,
                connected=p.websocket is not None,
            )
            for p in ordered
        ]

    def all_ready(self) -> bool:
        if len(self.players) != MAX_PLAYERS:
            return False
        return all(p.ready for p in self.players.values())

    def assign_seats(self) -> None:
        for i, pid in enumerate(sorted(self.players.keys(), key=lambda x: self.players[x].name)):
            self.players[pid].seat = i

    def start_meta_game(self) -> None:
        self.assign_seats()
        ids = [self.players[pid].id for pid in sorted(self.players.keys(), key=lambda x: self.players[x].seat or 0)]
        names = [self.players[pid].name for pid in sorted(self.players.keys(), key=lambda x: self.players[x].seat or 0)]
        self.meta = MetaGameManager(ids, names)
        self.pending_match = 1
        self.phase = RoomPhase.MATCH_INTRO

    def start_match(self, match_num: int) -> None:
        if self.meta is None:
            raise RuntimeError("Meta game not started")
        king_seat = self.meta.starting_king_seat_for_match(match_num)
        ids = self.meta.player_ids
        names = self.meta.player_names
        self.session = GameSession(ids, names, starting_king_seat=king_seat, seed=hash(self.code) + match_num)
        self.meta.record_match_start(match_num, self.session.state)
        self.pending_match = match_num
        self.phase = RoomPhase.PLAYING

    def finish_match(self) -> dict[str, Any]:
        if self.session is None or self.meta is None:
            raise RuntimeError("No active match")
        result = self.meta.compute_match_scores(self.session.state)
        self.phase = RoomPhase.MATCH_END
        return {
            "match_number": result.match_number,
            "winner_player_id": result.winner_player_id,
            "winner_started_as_king": result.winner_started_as_king,
            "points_awarded": result.points_awarded,
            "placements": result.placements,
            "meta": self.meta.to_dict(),
        }

    def check_game_over(self) -> bool:
        return self.meta is not None and self.meta.is_game_over()

    def get_game_end_payload(self) -> dict[str, Any]:
        if self.meta is None:
            return {}
        winners = self.meta.determine_winners()
        return {
            "winners": winners,
            "winner_names": [self.players[w].name for w in winners if w in self.players],
            "meta": self.meta.to_dict(),
            "co_winners": len(winners) > 1,
        }


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, GameRoom] = {}
        self.player_to_room: dict[str, str] = {}
        self.token_to_player: dict[str, tuple[str, str]] = {}

    def create_room(self, host_id: str, host_name: str) -> GameRoom:
        code = generate_room_code()
        while code in self.rooms:
            code = generate_room_code()
        room = GameRoom(code=code, host_id=host_id)
        player = ConnectedPlayer(id=host_id, name=host_name)
        room.players[host_id] = player
        self.rooms[code] = room
        self.player_to_room[host_id] = code
        self.token_to_player[player.reconnect_token] = (code, host_id)
        return room

    def get_room(self, code: str) -> GameRoom | None:
        return self.rooms.get(code.upper())

    def join_room(self, code: str, player_id: str, name: str) -> GameRoom:
        room = self.get_room(code)
        if room is None:
            raise ValueError("Room not found")
        if len(room.players) >= MAX_PLAYERS:
            raise ValueError("Room is full")
        if player_id in room.players:
            room.players[player_id].name = name
            return room
        player = ConnectedPlayer(id=player_id, name=name)
        room.players[player_id] = player
        self.player_to_room[player_id] = code.upper()
        self.token_to_player[player.reconnect_token] = (code.upper(), player_id)
        return room

    def reconnect(self, token: str, websocket: WebSocket) -> tuple[GameRoom, ConnectedPlayer]:
        entry = self.token_to_player.get(token)
        if entry is None:
            raise ValueError("Invalid reconnect token")
        code, player_id = entry
        room = self.rooms.get(code)
        if room is None:
            raise ValueError("Room no longer exists")
        player = room.players.get(player_id)
        if player is None:
            raise ValueError("Player not found")
        player.websocket = websocket
        return room, player

    async def broadcast(self, room: GameRoom, message: ServerMessage) -> None:
        dead: list[str] = []
        for pid, player in room.players.items():
            if player.websocket is None:
                continue
            try:
                await player.websocket.send_text(message.model_dump_json())
            except Exception:
                player.websocket = None
                dead.append(pid)

    async def send_to(self, player: ConnectedPlayer, message: ServerMessage) -> None:
        if player.websocket is None:
            return
        try:
            await player.websocket.send_text(message.model_dump_json())
        except Exception:
            player.websocket = None

    async def broadcast_game_state(self, room: GameRoom) -> None:
        if room.session is None:
            return
        session = room.session
        for pid, player in room.players.items():
            public = session.build_public_state().model_dump()
            private = session.build_private_state(pid).model_dump()
            dec = session.build_decision_info()
            msg = ServerMessage(
                type=ServerMessageType.GAME_STATE,
                payload={
                    "public": public,
                    "private": private,
                    "decision": dec.model_dump() if dec else None,
                    "your_seat": player.seat,
                    "phase": room.phase.value,
                    "match_number": room.pending_match,
                    "meta": room.meta.to_dict() if room.meta else None,
                },
            )
            await self.send_to(player, msg)

        dec = session.build_decision_info()
        if dec:
            await self.broadcast(
                room,
                ServerMessage(
                    type=ServerMessageType.DECISION_REQUIRED,
                    payload={
                        "decision": dec.model_dump(),
                        "seat_player_id": session.player_id_for_seat(dec.seat),
                        "seat_player_name": session.player_names[dec.seat],
                    },
                ),
            )

        for event in session.new_events():
            await self.broadcast(
                room,
                ServerMessage(type=ServerMessageType.EVENT, payload={"event": event}),
            )

    async def handle_action(
        self, room: GameRoom, player_id: str, payload: dict[str, Any]
    ) -> None:
        if room.session is None or room.phase != RoomPhase.PLAYING:
            return
        session = room.session
        dec = session.current_decision()
        if dec is None:
            return
        player_seat = room.players[player_id].seat
        if player_seat != dec.seat:
            raise ValueError("Not your turn")

        action = HumanAction(
            action_type=payload.get("action_type", "pass"),
            payload=payload.get("data", payload),
        )
        session.apply_action(action)

        if session.done:
            match_end = room.finish_match()
            await self.broadcast(
                room,
                ServerMessage(type=ServerMessageType.MATCH_END, payload=match_end),
            )
            if room.check_game_over():
                room.phase = RoomPhase.GAME_END
                await self.broadcast(
                    room,
                    ServerMessage(
                        type=ServerMessageType.GAME_END,
                        payload=room.get_game_end_payload(),
                    ),
                )
            else:
                room.pending_match = match_end["match_number"] + 1
                room.phase = RoomPhase.MATCH_INTRO
            return

        await self.broadcast_game_state(room)

    async def handle_proposal_response(
        self, room: GameRoom, player_id: str, accept: bool, proposal_id: str
    ) -> None:
        if room.session is None:
            return
        session = room.session
        dec = session.current_decision()
        if dec is None or dec.dtype.value != "negotiation":
            return
        player_seat = room.players[player_id].seat
        if player_seat != dec.seat:
            raise ValueError("Not your turn")

        action_type = "accept_proposal" if accept else "reject_proposal"
        session.apply_action(
            HumanAction(action_type=action_type, payload={"proposal_id": proposal_id})
        )

        if session.done:
            match_end = room.finish_match()
            await self.broadcast(
                room,
                ServerMessage(type=ServerMessageType.MATCH_END, payload=match_end),
            )
            if room.check_game_over():
                room.phase = RoomPhase.GAME_END
                await self.broadcast(
                    room,
                    ServerMessage(
                        type=ServerMessageType.GAME_END,
                        payload=room.get_game_end_payload(),
                    ),
                )
            else:
                room.pending_match = match_end["match_number"] + 1
                room.phase = RoomPhase.MATCH_INTRO
            return

        await self.broadcast_game_state(room)
