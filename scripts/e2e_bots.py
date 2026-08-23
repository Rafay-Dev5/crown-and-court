"""Fill a lobby with 3 bot WebSocket clients for local e2e testing."""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

import websockets


async def bot(name: str, code: str, uri: str = "ws://127.0.0.1:8000/ws") -> None:
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "join",
                    "payload": {
                        "action": "join",
                        "code": code,
                        "name": name,
                        "player_id": str(uuid.uuid4()),
                    },
                }
            )
        )
        readied = False
        while True:
            msg = json.loads(await ws.recv())
            t = msg["type"]
            p = msg.get("payload") or {}

            if t == "lobby_state" and not readied:
                me = next((x for x in p["players"] if x["id"] == p["your_id"]), None)
                if me and not me.get("ready"):
                    await ws.send(json.dumps({"type": "ready", "payload": {"ready": True}}))
                    readied = True

            elif t == "game_state":
                decision = p.get("decision")
                your_seat = p.get("your_seat")
                if decision and decision.get("seat") == your_seat:
                    dtype = decision.get("dtype")
                    if dtype == "negotiation":
                        await ws.send(
                            json.dumps({"type": "action", "payload": {"action_type": "pass", "data": {}}})
                        )
                    elif dtype == "play":
                        n = int(decision.get("context", {}).get("n_play", 2))
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "action",
                                    "payload": {
                                        "action_type": "play",
                                        "data": {"card_indices": list(range(n))},
                                    },
                                }
                            )
                        )
                    elif dtype == "choice":
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "action",
                                    "payload": {
                                        "action_type": "choice",
                                        "data": {"choice_index": 0},
                                    },
                                }
                            )
                        )

            elif t in ("match_end", "game_end"):
                return


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/e2e_bots.py ROOM_CODE")
        sys.exit(1)
    code = sys.argv[1].upper()
    await asyncio.gather(bot("Alex", code), bot("Sam", code), bot("Jordan", code))


if __name__ == "__main__":
    asyncio.run(main())
