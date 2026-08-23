from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import json


DB_PATH = Path("game_logs/balance_history.db")


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sweep_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            card_set_version TEXT,
            games_run INTEGER,
            bot_mode TEXT,
            metrics_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def log_sweep_run(
    sweep_result: dict[str, Any],
    bot_mode: str = "league",
    db_path: Path | str | None = None,
) -> int:
    conn = _connect(db_path)
    cur = conn.execute(
        """
        INSERT INTO sweep_runs (created_at, card_set_version, games_run, bot_mode, metrics_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            sweep_result.get("card_set_version"),
            sweep_result.get("games_run"),
            bot_mode,
            json.dumps(sweep_result.get("metrics", {})),
        ),
    )
    conn.commit()
    row_id = int(cur.lastrowid)
    conn.close()
    return row_id


def fetch_recent_runs(limit: int = 10, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT id, created_at, card_set_version, games_run, bot_mode FROM sweep_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
