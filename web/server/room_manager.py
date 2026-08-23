from __future__ import annotations

import asyncio
import random
import string
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import WebSocket

from web.server.bots import bot_should_accept, decide_bot_action, unused_bot_profiles
from web.server.game_session import GameSession, HumanAction
from web.server.meta_game import MetaGameManager, TOTAL_MATCHES
from web.server.protocol import PlayerInfo, ServerMessage, ServerMessageType

_room_bot_locks: dict[str, asyncio.Lock] = {}


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
    is_bot: bool = False
    bot_key: str | None = None


@dataclass
class GameRoom:
    code: str
    host_id: str
    players: dict[str, ConnectedPlayer] = field(default_factory=dict)
    phase: RoomPhase = RoomPhase.LOBBY
    meta: MetaGameManager | None = None
    session: GameSession | None = None
    pending_match: int = 0
    reveal_acks: set[str] = field(default_factory=set)

    def player_list(self) -> list[PlayerInfo]:
        ordered = sorted(self.players.values(), key=lambda p: p.seat if p.seat is not None else 99)
        return [
            PlayerInfo(
                id=p.id,
                name=p.name,
                seat=p.seat,
                ready=p.ready,
                connected=p.websocket is not None or p.is_bot,
                is_bot=p.is_bot,
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
        self.session = GameSession(
            ids,
            names,
            starting_king_seat=king_seat,
            seed=abs(hash(self.code)) % (2**31 - 1) + match_num,
        )
        self.meta.record_match_start(match_num, self.session.state)
        self.pending_match = match_num
        self.phase = RoomPhase.PLAYING
        self.reveal_acks = set()

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
        if room.phase != RoomPhase.LOBBY:
            raise ValueError("Game already started — ask the host for a new lobby")
        if len(room.players) >= MAX_PLAYERS and player_id not in room.players:
            raise ValueError("Room is full")
        if player_id in room.players:
            room.players[player_id].name = name
            return room
        player = ConnectedPlayer(id=player_id, name=name)
        room.players[player_id] = player
        self.player_to_room[player_id] = code.upper()
        self.token_to_player[player.reconnect_token] = (code.upper(), player_id)
        return room

    def fill_bots(self, room: GameRoom, count: int | None = None) -> list[ConnectedPlayer]:
        if room.phase != RoomPhase.LOBBY:
            raise ValueError("Bots can only be added in the lobby")
        empty = MAX_PLAYERS - len(room.players)
        if empty <= 0:
            return []
        n = empty if count is None else min(int(count), empty)
        used = {p.bot_key for p in room.players.values() if p.bot_key}
        added: list[ConnectedPlayer] = []
        for key, name, _blurb in unused_bot_profiles(used):
            if n <= 0:
                break
            pid = f"bot-{key}-{uuid.uuid4().hex[:6]}"
            player = ConnectedPlayer(
                id=pid,
                name=name,
                ready=True,
                is_bot=True,
                bot_key=key,
            )
            room.players[pid] = player
            self.player_to_room[pid] = room.code
            self.token_to_player[player.reconnect_token] = (room.code, pid)
            added.append(player)
            n -= 1
        return added

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

    async def broadcast_lobby(self, room: GameRoom) -> None:
        """Send each player a personalized lobby payload (correct your_id / token)."""
        for pid, player in room.players.items():
            payload = {
                "code": room.code,
                "host_id": room.host_id,
                "players": [p.model_dump() for p in room.player_list()],
                "your_id": pid,
                "your_seat": player.seat,
                "reconnect_token": player.reconnect_token,
                "phase": room.phase.value,
                "can_start": room.all_ready() and pid == room.host_id,
                "meta": room.meta.to_dict() if room.meta else None,
            }
            await self.send_to(
                player,
                ServerMessage(type=ServerMessageType.LOBBY_STATE, payload=payload),
            )

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
        public = session.build_public_state().model_dump()
        dec = session.build_decision_info()
        dec_payload = dec.model_dump() if dec else None
        for pid, player in room.players.items():
            private = session.build_private_state(pid).model_dump()
            msg = ServerMessage(
                type=ServerMessageType.GAME_STATE,
                payload={
                    "public": public,
                    "private": private,
                    "decision": dec_payload,
                    "your_seat": player.seat,
                    "phase": room.phase.value,
                    "match_number": room.pending_match,
                    "meta": room.meta.to_dict() if room.meta else None,
                    "reveal_acks": list(room.reveal_acks),
                },
            )
            await self.send_to(player, msg)

        if dec:
            await self.broadcast(
                room,
                ServerMessage(
                    type=ServerMessageType.DECISION_REQUIRED,
                    payload={
                        "decision": dec_payload,
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

    def _reveal_ready(self, room: GameRoom) -> bool:
        needed: list[str] = []
        for player in room.players.values():
            if player.is_bot:
                room.reveal_acks.add(player.id)
                continue
            if player.websocket is None:
                continue
            needed.append(player.id)
        if not needed:
            return True
        return all(pid in room.reveal_acks for pid in needed)

    async def _finish_if_done(self, room: GameRoom) -> bool:
        session = room.session
        if session is None or not session.done:
            return False
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
        return True

    async def handle_action(
        self, room: GameRoom, player_id: str, payload: dict[str, Any]
    ) -> None:
        if room.session is None or room.phase != RoomPhase.PLAYING:
            return
        session = room.session
        dec = session.current_decision()
        if dec is None:
            return
        action_type = payload.get("action_type", "pass")
        is_reveal = dec.dtype.value == "reveal" or action_type == "continue_reveal"
        player_seat = room.players[player_id].seat
        if is_reveal:
            room.reveal_acks.add(player_id)
            if not self._reveal_ready(room):
                await self.broadcast_game_state(room)
                return
            room.reveal_acks.clear()
            session.apply_action(HumanAction(action_type="continue_reveal"))
            if await self._finish_if_done(room):
                return
            await self.broadcast_game_state(room)
            await self.drive_bots(room)
            return

        if player_seat != dec.seat:
            raise ValueError("Not your turn")

        action = HumanAction(
            action_type=action_type,
            payload=payload.get("data", payload),
        )
        session.apply_action(action)
        room.reveal_acks.clear()

        if await self._finish_if_done(room):
            return

        await self.broadcast_game_state(room)
        await self.drive_bots(room)

    async def handle_proposal_response(
        self,
        room: GameRoom,
        player_id: str,
        accept: bool,
        proposal_id: str,
        fulfillment_cards: list[str] | None = None,
    ) -> None:
        """Accept/reject a pending proposal without consuming the player's negotiation turn.

        Responding mid-phase must not skip the last seats' chance to propose trades.
        """
        if room.session is None or room.phase != RoomPhase.PLAYING:
            return
        session = room.session
        state = session.state
        if state is None or state.phase.value != "negotiation":
            raise ValueError("Proposals can only be answered during negotiation")

        player_seat = room.players[player_id].seat
        if player_seat is None:
            raise ValueError("Player has no seat")

        proposal = next(
            (p for p in state.pending_proposals if p.get("id") == proposal_id),
            None,
        )
        if proposal is None or proposal.get("status") not in ("pending", "pending_confirm"):
            raise ValueError("Proposal not found")

        is_target = proposal.get("target") == player_seat
        is_alliance_target = player_seat in (proposal.get("targets") or [])
        is_proposer = proposal.get("proposer") == player_seat

        from engine.negotiation import accept_proposal, confirm_proposal, reject_proposal

        if accept:
            if proposal.get("status") == "pending_confirm":
                if not is_proposer:
                    raise ValueError("Only the proposer can confirm after cards are revealed")
                ok = confirm_proposal(state, player_seat, proposal_id)
            else:
                if not is_target and not is_alliance_target:
                    raise ValueError("This proposal is not addressed to you")
                ok = accept_proposal(
                    state,
                    player_seat,
                    proposal_id,
                    fulfillment_cards=fulfillment_cards,
                )
        else:
            if not is_target and not is_alliance_target and not (
                proposal.get("status") == "pending_confirm" and is_proposer
            ):
                raise ValueError("This proposal is not addressed to you")
            ok = reject_proposal(state, player_seat, proposal_id)
        if not ok:
            raise ValueError("Could not update proposal")

        # Do NOT step DecisionEngine — leave the current negotiator's turn intact.
        await self.broadcast_game_state(room)
        await self.drive_bots(room)

    async def drive_bots(self, room: GameRoom) -> None:
        """Advance bot seats, auto-answer their proposals, and auto-continue reveals."""
        lock = _room_bot_locks.setdefault(room.code, asyncio.Lock())
        if lock.locked():
            return
        async with lock:
            while room.session is not None and room.phase == RoomPhase.PLAYING:
                if await self._bots_answer_proposals(room):
                    await self.broadcast_game_state(room)
                    continue

                dec = room.session.current_decision()
                if dec is None:
                    break

                if dec.dtype.value == "reveal":
                    for player in room.players.values():
                        if player.is_bot:
                            room.reveal_acks.add(player.id)
                    if self._reveal_ready(room):
                        room.reveal_acks.clear()
                        room.session.apply_action(HumanAction(action_type="continue_reveal"))
                        if await self._finish_if_done(room):
                            return
                        await self.broadcast_game_state(room)
                        continue
                    await self.broadcast_game_state(room)
                    break

                pid = room.session.player_id_for_seat(dec.seat)
                actor = room.players.get(pid)
                if actor is None or not actor.is_bot:
                    break

                await asyncio.sleep(0.2)
                action = decide_bot_action(actor.bot_key or "exploit", room.session, dec)
                room.session.apply_action(action)
                room.reveal_acks.clear()
                if await self._finish_if_done(room):
                    return
                await self.broadcast_game_state(room)

    async def _bots_answer_proposals(self, room: GameRoom) -> bool:
        session = room.session
        if session is None or session.state.phase.value != "negotiation":
            return False
        from engine.negotiation import (
            _card_count_request,
            accept_proposal,
            confirm_proposal,
            reject_proposal,
        )

        for player in room.players.values():
            if not player.is_bot or player.seat is None:
                continue

            # Confirm trades where we proposed and they revealed cards.
            to_confirm = [
                p
                for p in session.state.pending_proposals
                if p.get("status") == "pending_confirm" and p.get("proposer") == player.seat
            ]
            if to_confirm:
                ok = confirm_proposal(session.state, player.seat, to_confirm[0]["id"])
                return bool(ok)

            pending = [
                p
                for p in session.state.pending_proposals
                if p.get("status") == "pending"
                and (
                    p.get("target") == player.seat
                    or player.seat in (p.get("targets") or [])
                )
            ]
            if not pending:
                continue
            proposal = pending[0]
            accept = bot_should_accept(
                player.bot_key or "exploit", proposal, session.rng
            )
            if accept:
                needed = _card_count_request(proposal.get("request"))
                fulfillment: list[str] | None = None
                if needed > 0:
                    hand = session.state.seats[player.seat].hand
                    if len(hand) < needed:
                        ok = reject_proposal(session.state, player.seat, proposal["id"])
                        return bool(ok)
                    fulfillment = [c["id"] for c in hand[:needed]]
                ok = accept_proposal(
                    session.state,
                    player.seat,
                    proposal["id"],
                    fulfillment_cards=fulfillment,
                )
            else:
                ok = reject_proposal(session.state, player.seat, proposal["id"])
            return bool(ok)
        return False
