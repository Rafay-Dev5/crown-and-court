"""Run four distinct bots through a full online session (lobby → 4 matches).

Usage:
  python scripts/play_bot_game.py                  # local ws://127.0.0.1:8000/ws
  python scripts/play_bot_game.py wss://host/ws
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import websockets

BOTS = [
    ("The Hoarder", "hoard"),
    ("The Aggressor", "aggressive"),
    ("The Diplomat", "ally_neighbor"),
    ("The Opportunist", "exploit"),
]


def _send(ws, typ: str, payload: dict | None = None):
    return ws.send(json.dumps({"type": typ, "payload": payload or {}}))


async def run_bot(name: str, key: str, uri: str, code_holder: dict, host: bool) -> None:
    player_id = f"bot-{key}-{uuid.uuid4().hex[:6]}"
    async with websockets.connect(uri, max_size=2**22) as ws:
        if host:
            await _send(ws, "join", {"action": "create", "name": name, "player_id": player_id})
        else:
            for _ in range(50):
                if code_holder.get("code"):
                    break
                await asyncio.sleep(0.05)
            await _send(ws, "join", {
                "action": "join",
                "code": code_holder["code"],
                "name": name,
                "player_id": player_id,
            })

        your_id = None
        your_seat = None
        readied = False
        started = False
        began = set()
        last_decision = None

        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=120)
            msg = json.loads(raw)
            typ = msg["type"]
            p = msg.get("payload") or {}

            if typ == "error":
                print(f"[{name}] error: {p.get('message')}")
                continue

            if typ == "lobby_state":
                your_id = p.get("your_id") or your_id
                if p.get("code"):
                    code_holder["code"] = p["code"]
                    if host:
                        print(f"Room {p['code']}")
                if not readied:
                    await _send(ws, "ready", {"ready": True})
                    readied = True
                players = p.get("players") or []
                if host and not started and len(players) == 4 and all(x.get("ready") for x in players):
                    await _send(ws, "start")
                    started = True

            elif typ == "match_intro":
                match = int(p.get("match_number") or 1)
                if host and match not in began:
                    began.add(match)
                    await _send(ws, "begin_match", {"match_number": match})

            elif typ == "game_state":
                your_seat = p.get("your_seat", your_seat)
                decision = p.get("decision")
                if not decision:
                    continue
                token = (decision.get("decision_id"), decision.get("dtype"))
                if token == last_decision:
                    continue
                dtype = decision.get("dtype")
                if dtype == "reveal":
                    last_decision = token
                    await _send(ws, "action", {"action_type": "continue_reveal", "data": {}})
                    continue
                if decision.get("seat") != your_seat:
                    continue
                last_decision = token
                if dtype == "negotiation":
                    if key == "ally_neighbor":
                        await _send(ws, "action", {
                            "action_type": "propose_alliance",
                            "data": {"targets": [((your_seat or 0) + 1) % 4], "terms": "neighbor pact"},
                        })
                    elif key == "aggressive":
                        await _send(ws, "action", {
                            "action_type": "propose_trade",
                            "data": {
                                "target": ((your_seat or 0) + 1) % 4,
                                "offer": {"gold": 40, "cards": []},
                                "request": {"gold": 0, "card_count": 1},
                            },
                        })
                    else:
                        await _send(ws, "action", {"action_type": "pass", "data": {}})
                elif dtype == "play":
                    n = int((decision.get("context") or {}).get("n_play") or 2)
                    await _send(ws, "action", {
                        "action_type": "play",
                        "data": {"card_indices": list(range(n))},
                    })
                elif dtype == "target":
                    legal = (decision.get("context") or {}).get("legal_targets") or [0]
                    await _send(ws, "action", {
                        "action_type": "choose_target",
                        "data": {"target_seat": legal[0]},
                    })
                elif dtype == "choice":
                    await _send(ws, "action", {
                        "action_type": "choice",
                        "data": {"choice_index": 0},
                    })
                elif dtype == "discard":
                    count = int((decision.get("context") or {}).get("count") or 1)
                    await _send(ws, "action", {
                        "action_type": "discard",
                        "data": {"card_indices": list(range(count))},
                    })

            elif typ == "match_end":
                print(f"[{name}] match {p.get('match_number')} over")
                if host:
                    await _send(ws, "next_match", {})

            elif typ == "game_end":
                print(f"[{name}] game over — winners: {p.get('winner_names')}")
                return


async def main() -> None:
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8000/ws"
    code_holder: dict = {}
    tasks = [
        run_bot(name, key, uri, code_holder, host=(i == 0))
        for i, (name, key) in enumerate(BOTS)
    ]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
