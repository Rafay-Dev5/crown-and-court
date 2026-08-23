from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.server.protocol import ClientMessage, ClientMessageType, ServerMessage, ServerMessageType
from web.server.room_manager import RoomManager, RoomPhase

app = FastAPI(title="Crown & Court Multiplayer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = RoomManager()

STATIC_DIR = ROOT / "web" / "client" / "dist"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "rooms": str(len(rooms.rooms))}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    player_id: str | None = None
    room_code: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = ClientMessage.model_validate_json(raw)
            except Exception as exc:
                await _send_error(websocket, f"Invalid message: {exc}")
                continue
            try:
                player_id, room_code = await handle_message(
                    websocket, msg, player_id, room_code
                )
            except ValueError as exc:
                await _send_error(websocket, str(exc))
            except Exception as exc:
                await _send_error(websocket, f"Server error: {exc}")
    except WebSocketDisconnect:
        if room_code and player_id:
            room = rooms.get_room(room_code)
            if room and player_id in room.players:
                room.players[player_id].websocket = None
                try:
                    await rooms.broadcast_lobby(room)
                except Exception:
                    pass


async def handle_message(
    websocket: WebSocket,
    msg: ClientMessage,
    player_id: str | None,
    room_code: str | None,
) -> tuple[str | None, str | None]:
    if msg.type == ClientMessageType.JOIN:
        return await _handle_join(websocket, msg)

    if msg.type == ClientMessageType.RECONNECT:
        return await _handle_reconnect(websocket, msg)

    if player_id is None or room_code is None:
        await _send_error(websocket, "Not connected to a room")
        return player_id, room_code

    room = rooms.get_room(room_code)
    if room is None:
        await _send_error(websocket, "Room not found")
        return player_id, room_code

    if msg.type == ClientMessageType.READY:
        if player_id not in room.players:
            await _send_error(websocket, "Player not in room")
            return player_id, room_code
        if room.phase != RoomPhase.LOBBY:
            await _send_error(websocket, "Cannot change ready outside lobby")
            return player_id, room_code
        # Absolute ready state (not toggle) — avoids race flips under concurrent updates.
        if "ready" in msg.payload:
            room.players[player_id].ready = bool(msg.payload.get("ready"))
        else:
            room.players[player_id].ready = True
        await rooms.broadcast_lobby(room)

    elif msg.type == ClientMessageType.START:
        if player_id != room.host_id:
            await _send_error(websocket, "Only host can start")
            return player_id, room_code
        if not room.all_ready():
            await _send_error(websocket, "All players must be ready")
            return player_id, room_code
        room.start_meta_game()
        king_seat = room.meta.starting_king_seat_for_match(1) if room.meta else 0
        king_name = room.meta.player_names[king_seat] if room.meta else ""
        # Refresh lobby seats for every client, then show match intro.
        await rooms.broadcast_lobby(room)
        await rooms.broadcast(
            room,
            ServerMessage(
                type=ServerMessageType.MATCH_INTRO,
                payload={
                    "match_number": 1,
                    "total_matches": 4,
                    "starting_king_seat": king_seat,
                    "starting_king_name": king_name,
                    "meta": room.meta.to_dict() if room.meta else None,
                },
            ),
        )

    elif msg.type == ClientMessageType.BEGIN_MATCH:
        match_num = int(msg.payload.get("match_number", room.pending_match or 1))
        if match_num < 1 or match_num > 4:
            await _send_error(websocket, "Invalid match number")
            return player_id, room_code
        if room.phase not in (RoomPhase.MATCH_INTRO, RoomPhase.MATCH_END):
            # Allow begin from match_intro; also after match_end client navigates to intro.
            if room.phase != RoomPhase.MATCH_INTRO and room.pending_match != match_num:
                pass
        try:
            room.start_match(match_num)
        except Exception as exc:
            await _send_error(websocket, f"Failed to start match: {exc}")
            return player_id, room_code
        await rooms.broadcast_game_state(room)

    elif msg.type == ClientMessageType.ACTION:
        try:
            await rooms.handle_action(room, player_id, msg.payload)
        except ValueError as e:
            await _send_error(websocket, str(e))
        except Exception as e:
            await _send_error(websocket, f"Action failed: {e}")

    elif msg.type == ClientMessageType.ACCEPT_PROPOSAL:
        try:
            await rooms.handle_proposal_response(
                room, player_id, True, msg.payload.get("proposal_id", "")
            )
        except ValueError as e:
            await _send_error(websocket, str(e))

    elif msg.type == ClientMessageType.REJECT_PROPOSAL:
        try:
            await rooms.handle_proposal_response(
                room, player_id, False, msg.payload.get("proposal_id", "")
            )
        except ValueError as e:
            await _send_error(websocket, str(e))

    return player_id, room_code


async def _handle_join(
    websocket: WebSocket, msg: ClientMessage
) -> tuple[str, str]:
    action = msg.payload.get("action", "create")
    name = msg.payload.get("name", "Player").strip()[:24] or "Player"
    player_id = msg.payload.get("player_id") or str(uuid.uuid4())

    if action == "create":
        room = rooms.create_room(player_id, name)
        room.players[player_id].websocket = websocket
        await rooms.send_to(
            room.players[player_id],
            ServerMessage(
                type=ServerMessageType.LOBBY_STATE,
                payload=_lobby_payload(room, player_id),
            ),
        )
        return player_id, room.code

    code = (msg.payload.get("code") or "").upper().strip().replace(" ", "")
    if not code:
        raise ValueError("Room code required")
    room = rooms.join_room(code, player_id, name)
    room.players[player_id].websocket = websocket
    await rooms.broadcast_lobby(room)
    return player_id, room.code


async def _handle_reconnect(
    websocket: WebSocket, msg: ClientMessage
) -> tuple[str | None, str | None]:
    token = msg.payload.get("token", "")
    try:
        room, player = rooms.reconnect(token, websocket)
    except ValueError as exc:
        await _send_error(websocket, str(exc))
        return None, None

    payload = _lobby_payload(room, player.id)
    payload["reconnected"] = True

    if room.phase == RoomPhase.PLAYING and room.session:
        await rooms.send_to(
            player,
            ServerMessage(type=ServerMessageType.LOBBY_STATE, payload=payload),
        )
        await rooms.broadcast_game_state(room)
    elif room.phase == RoomPhase.MATCH_INTRO:
        await rooms.send_to(
            player,
            ServerMessage(
                type=ServerMessageType.MATCH_INTRO,
                payload={
                    "match_number": room.pending_match,
                    "total_matches": 4,
                    "starting_king_seat": (
                        room.meta.starting_king_seat_for_match(room.pending_match)
                        if room.meta
                        else 0
                    ),
                    "starting_king_name": (
                        room.meta.player_names[
                            room.meta.starting_king_seat_for_match(room.pending_match)
                        ]
                        if room.meta
                        else ""
                    ),
                    "meta": room.meta.to_dict() if room.meta else None,
                },
            ),
        )
    elif room.phase == RoomPhase.MATCH_END:
        await rooms.send_to(
            player,
            ServerMessage(type=ServerMessageType.LOBBY_STATE, payload=payload),
        )
    elif room.phase == RoomPhase.GAME_END:
        await rooms.send_to(
            player,
            ServerMessage(
                type=ServerMessageType.GAME_END,
                payload=room.get_game_end_payload(),
            ),
        )
    else:
        await rooms.send_to(
            player,
            ServerMessage(type=ServerMessageType.LOBBY_STATE, payload=payload),
        )

    return player.id, room.code


def _lobby_payload(room, player_id: str) -> dict:
    player = room.players[player_id]
    return {
        "code": room.code,
        "host_id": room.host_id,
        "players": [p.model_dump() for p in room.player_list()],
        "your_id": player_id,
        "your_seat": player.seat,
        "reconnect_token": player.reconnect_token,
        "phase": room.phase.value,
        "can_start": room.all_ready() and player_id == room.host_id,
        "meta": room.meta.to_dict() if room.meta else None,
    }


async def _send_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_text(
        ServerMessage(type=ServerMessageType.ERROR, payload={"message": message}).model_dump_json()
    )


def _mount_static_client() -> None:
    """Serve the built React app from the same origin as the WebSocket (production)."""
    if not STATIC_DIR.is_dir():
        return

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static-assets")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    async def serve_spa(path: str) -> FileResponse:
        # Let API routes win; everything else falls back to the SPA shell.
        if path in ("health", "ws"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        candidate = STATIC_DIR / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")


_mount_static_client()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("web.server.main:app", host="0.0.0.0", port=port, reload=True)
