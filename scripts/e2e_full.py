"""Full WebSocket e2e against local or production."""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

import websockets

URI = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8000/ws"


async def recv_matching(ws, types, timeout=20.0):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        raw = await asyncio.wait_for(ws.recv(), timeout=max(0.05, end - asyncio.get_event_loop().time()))
        msg = json.loads(raw)
        if msg.get("type") in types:
            return msg
    raise TimeoutError(f"timeout waiting for {types}")


async def drain_and_act(ws, name: str, your_id: str, is_host: bool, stop_event: asyncio.Event, shared: dict):
    identity_bugs = 0
    while not stop_event.is_set():
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        msg = json.loads(raw)
        t = msg.get("type")
        p = msg.get("payload") or {}

        if t == "error":
            print(f"[{name}] ERROR {p}")
            continue

        if t == "lobby_state":
            if p.get("your_id") != your_id:
                identity_bugs += 1
                print(f"[{name}] IDENTITY BUG got your_id={p.get('your_id')} expected={your_id}")
                your_id = p["your_id"]
            players = p.get("players") or []
            me = next((x for x in players if x["id"] == your_id), None)
            print(f"[{name}] lobby n={len(players)} ready={me and me.get('ready')} can_start={p.get('can_start')}")
            if me and not me.get("ready") and not shared.get(f"ready_{name}"):
                shared[f"ready_{name}"] = True
                await ws.send(json.dumps({"type": "ready", "payload": {"ready": True}}))
            if is_host and p.get("can_start") and not shared.get("started"):
                shared["started"] = True
                await ws.send(json.dumps({"type": "start"}))

        elif t == "match_intro":
            print(f"[{name}] match_intro king={p.get('starting_king_name')} match={p.get('match_number')}")
            shared["match_intro"] = True
            if is_host and not shared.get("began"):
                shared["began"] = True
                await ws.send(json.dumps({"type": "begin_match", "payload": {"match_number": p.get("match_number", 1)}}))

        elif t == "game_state":
            decision = p.get("decision")
            your_seat = p.get("your_seat")
            pub = p.get("public") or {}
            private = p.get("private") or {}
            hand = private.get("hand") or []
            print(
                f"[{name}] game r={pub.get('current_round')}/{pub.get('n_rounds')} "
                f"phase={pub.get('phase')} seat={your_seat} hand={len(hand)} "
                f"dec={decision and decision.get('dtype')}"
            )
            shared["saw_game"] = True
            if decision and decision.get("seat") == your_seat:
                dtype = decision.get("dtype")
                if dtype == "negotiation":
                    await ws.send(json.dumps({"type": "action", "payload": {"action_type": "pass", "data": {}}}))
                elif dtype == "play":
                    n = int(decision.get("context", {}).get("n_play", 2))
                    await ws.send(
                        json.dumps(
                            {
                                "type": "action",
                                "payload": {"action_type": "play", "data": {"card_indices": list(range(n))}},
                            }
                        )
                    )
                elif dtype == "choice":
                    await ws.send(
                        json.dumps(
                            {
                                "type": "action",
                                "payload": {"action_type": "choice", "data": {"choice_index": 0}},
                            }
                        )
                    )
                elif dtype == "target":
                    legal = decision.get("context", {}).get("legal_targets") or [0]
                    await ws.send(
                        json.dumps(
                            {
                                "type": "action",
                                "payload": {
                                    "action_type": "choose_target",
                                    "data": {"target_seat": legal[0]},
                                },
                            }
                        )
                    )
                elif dtype == "discard":
                    count = int(decision.get("context", {}).get("count", 1))
                    await ws.send(
                        json.dumps(
                            {
                                "type": "action",
                                "payload": {
                                    "action_type": "discard",
                                    "data": {"card_indices": list(range(count))},
                                },
                            }
                        )
                    )
                elif dtype == "reveal":
                    await ws.send(
                        json.dumps(
                            {
                                "type": "action",
                                "payload": {"action_type": "continue_reveal", "data": {}},
                            }
                        )
                    )

        elif t == "match_end":
            print(f"[{name}] MATCH_END points={p.get('points_awarded')}")
            shared["match_end"] = p
            stop_event.set()
            return identity_bugs

        elif t == "game_end":
            print(f"[{name}] GAME_END winners={p.get('winner_names')}")
            shared["game_end"] = p
            stop_event.set()
            return identity_bugs

    return identity_bugs


async def run_player(name: str, code: str, is_host: bool, stop_event: asyncio.Event, shared: dict):
    pid = str(uuid.uuid4())
    async with websockets.connect(URI, open_timeout=30) as ws:
        action = "create" if is_host else "join"
        payload = {"action": action, "name": name, "player_id": pid}
        if not is_host:
            payload["code"] = code
        await ws.send(json.dumps({"type": "join", "payload": payload}))
        lobby = await recv_matching(ws, {"lobby_state", "error"})
        if lobby.get("type") == "error":
            raise RuntimeError(f"{name}: {lobby}")
        your_id = lobby["payload"]["your_id"]
        room = lobby["payload"]["code"]
        if is_host:
            shared["code"] = room
        print(f"[{name}] joined room={room} your_id={your_id}")
        bugs = await drain_and_act(ws, name, your_id, is_host, stop_event, shared)
        return bugs


async def main():
    print("=== E2E URI", URI)
    shared: dict = {}
    stop = asyncio.Event()

    # Create host first to obtain code, keep connection... actually use two-phase:
    host_pid = str(uuid.uuid4())
    async with websockets.connect(URI, open_timeout=30) as bootstrap:
        await bootstrap.send(
            json.dumps({"type": "join", "payload": {"action": "create", "name": "Bootstrap", "player_id": host_pid}})
        )
        lobby = await recv_matching(bootstrap, {"lobby_state", "error"})
        code = lobby["payload"]["code"]
        print("bootstrap room", code)
        # leave bootstrap disconnected — room remains with 1 disconnected player.
        # Better: start fresh room with 4 simultaneous joins where host creates.

    # Clean approach: host creates; others wait for code via shared event
    shared = {"code": None}
    stop = asyncio.Event()
    code_ready = asyncio.Event()

    async def host():
        pid = str(uuid.uuid4())
        async with websockets.connect(URI, open_timeout=30) as ws:
            await ws.send(json.dumps({"type": "join", "payload": {"action": "create", "name": "Host", "player_id": pid}}))
            lobby = await recv_matching(ws, {"lobby_state", "error"})
            shared["code"] = lobby["payload"]["code"]
            your_id = lobby["payload"]["your_id"]
            print(f"[Host] created {shared['code']} your_id={your_id}")
            code_ready.set()
            return await drain_and_act(ws, "Host", your_id, True, stop, shared)

    async def guest(name: str):
        await code_ready.wait()
        code = shared["code"]
        pid = str(uuid.uuid4())
        async with websockets.connect(URI, open_timeout=30) as ws:
            await ws.send(
                json.dumps({"type": "join", "payload": {"action": "join", "code": code, "name": name, "player_id": pid}})
            )
            lobby = await recv_matching(ws, {"lobby_state", "error"})
            if lobby.get("type") == "error":
                raise RuntimeError(lobby)
            your_id = lobby["payload"]["your_id"]
            print(f"[{name}] joined your_id={your_id} n={len(lobby['payload']['players'])}")
            return await drain_and_act(ws, name, your_id, False, stop, shared)

    results = await asyncio.gather(
        host(),
        guest("Alex"),
        guest("Sam"),
        guest("Jordan"),
        return_exceptions=True,
    )
    print("=== RESULTS", results)
    print("=== shared keys", {k: (v if k != "match_end" else "set") for k, v in shared.items()})
    bugs = sum(r for r in results if isinstance(r, int))
    ok = shared.get("saw_game") and shared.get("match_end")
    print("=== PASS" if ok and bugs == 0 else f"=== FAIL saw_game={shared.get('saw_game')} match_end={bool(shared.get('match_end'))} identity_bugs={bugs}")
    if not ok or bugs:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
