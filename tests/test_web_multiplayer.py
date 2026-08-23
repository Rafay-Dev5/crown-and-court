"""Web multiplayer integration tests."""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from web.server.main import app
from web.server.meta_game import MetaGameManager, WIN_POINTS_THRESHOLD
from web.server.game_session import GameSession, HumanAction


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_meta_game_king_defends():
    ids = ["p0", "p1", "p2", "p3"]
    names = ["A", "B", "C", "D"]
    meta = MetaGameManager(ids, names)
    session = GameSession(ids, names, starting_king_seat=0, seed=42)
    meta.record_match_start(1, session.state)

    while not session.done:
        dec = session.current_decision()
        if dec is None:
            break
        if dec.dtype.value == "negotiation":
            session.apply_action(HumanAction(action_type="pass"))
        elif dec.dtype.value == "play":
            n = dec.context.get("n_play", 2)
            session.apply_action(
                HumanAction(action_type="play", payload={"card_indices": list(range(n))})
            )
        elif dec.dtype.value == "choice":
            session.apply_action(
                HumanAction(action_type="choice", payload={"choice_index": 0})
            )
        elif dec.dtype.value == "reveal":
            session.apply_action(HumanAction(action_type="continue_reveal"))

    result = meta.compute_match_scores(session.state)
    assert result.winner_player_id in ids
    assert sum(result.points_awarded.values()) > 0


def test_meta_game_rotation():
    meta = MetaGameManager(["a", "b", "c", "d"], ["A", "B", "C", "D"])
    assert meta.starting_king_seat_for_match(1) == 0
    assert meta.starting_king_seat_for_match(2) == 1
    assert meta.starting_king_seat_for_match(3) == 2
    assert meta.starting_king_seat_for_match(4) == 3


def test_meta_game_end_conditions():
    meta = MetaGameManager(["a", "b", "c", "d"], ["A", "B", "C", "D"])
    meta.players["a"].total_points = WIN_POINTS_THRESHOLD
    assert meta.is_game_over()


def test_game_session_reset():
    session = GameSession(
        ["a", "b", "c", "d"], ["A", "B", "C", "D"], starting_king_seat=2, seed=1
    )
    assert session.state.king_seat == 2
    assert session.state.num_players == 4
    assert session.state.n_rounds == 4


def test_websocket_create_and_join():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws1:
        ws1.send_json({"type": "join", "payload": {"action": "create", "name": "Host"}})
        msg1 = json.loads(ws1.receive_text())
        assert msg1["type"] == "lobby_state"
        code = msg1["payload"]["code"]

        with client.websocket_connect("/ws") as ws2:
            ws2.send_json(
                {"type": "join", "payload": {"action": "join", "code": code, "name": "P2"}}
            )
            msg2 = json.loads(ws2.receive_text())
            assert msg2["type"] == "lobby_state"
            assert len(msg2["payload"]["players"]) == 2


def test_practice_lobby_fills_three_named_bots():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "payload": {"action": "practice", "name": "Host"}})
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "lobby_state"
        names = {p["name"] for p in msg["payload"]["players"]}
        assert "Host" in names
        assert "The Hoarder" in names
        assert "The Aggressor" in names
        assert "The Diplomat" in names
        assert sum(1 for p in msg["payload"]["players"] if p.get("is_bot")) == 3


def test_four_bots_play_full_meta_game():
    from web.server.bots import decide_bot_action

    ids = ["hoard", "aggressive", "ally_neighbor", "exploit"]
    names = ["The Hoarder", "The Aggressor", "The Diplomat", "The Opportunist"]
    meta = MetaGameManager(ids, names)
    finished = 0
    for match in range(1, 5):
        if meta.is_game_over():
            break
        king = meta.starting_king_seat_for_match(match)
        session = GameSession(ids, names, starting_king_seat=king, seed=200 + match)
        meta.record_match_start(match, session.state)
        steps = 0
        while not session.done and steps < 8000:
            dec = session.current_decision()
            if dec is None:
                break
            if dec.dtype.value == "reveal":
                session.apply_action(HumanAction(action_type="continue_reveal"))
            else:
                key = ids[dec.seat]
                session.apply_action(decide_bot_action(key, session, dec))
            steps += 1
        assert session.done, f"match {match} did not finish after {steps} steps"
        meta.compute_match_scores(session.state)
        finished += 1
        public = session.build_public_state()
        assert all(hasattr(st, "name") for seat in public.seats for st in seat.statuses)
    assert finished >= 1
    winners = meta.determine_winners()
    assert winners
    assert all(w in ids for w in winners)


def test_websocket_ready_and_reconnect_token():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "payload": {"action": "create", "name": "Host"}})
        msg = json.loads(ws.receive_text())
        assert "reconnect_token" in msg["payload"]
        token = msg["payload"]["reconnect_token"]

        ws.send_json({"type": "ready"})
        ready_msg = json.loads(ws.receive_text())
        assert ready_msg["type"] == "lobby_state"
        host = next(p for p in ready_msg["payload"]["players"] if p["name"] == "Host")
        assert host["ready"] is True

    with client.websocket_connect("/ws") as ws2:
        ws2.send_json({"type": "reconnect", "payload": {"token": token}})
        msg = json.loads(ws2.receive_text())
        assert msg["type"] == "lobby_state"
        assert msg["payload"].get("reconnected") is True
