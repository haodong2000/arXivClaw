from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


class StateStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_papers (
                    arxiv_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    total_fetched INTEGER NOT NULL,
                    total_scored INTEGER NOT NULL,
                    total_sent INTEGER NOT NULL,
                    note TEXT
                )
                """
            )

    def is_processed(self, arxiv_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_papers WHERE arxiv_id = ? LIMIT 1", (arxiv_id,)
            ).fetchone()
        return row is not None

    def mark_processed_many(self, arxiv_ids: list[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = [(arxiv_id, now) for arxiv_id in arxiv_ids]
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO processed_papers (arxiv_id, processed_at) VALUES (?, ?)", rows
            )

    def create_run(self, run_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, started_at, status, total_fetched, total_scored, total_sent)
                VALUES (?, ?, 'running', 0, 0, 0)
                """,
                (run_id, datetime.now(timezone.utc).isoformat()),
            )

    def finish_run(
        self,
        run_id: str,
        status: str,
        total_fetched: int,
        total_scored: int,
        total_sent: int,
        note: str = "",
    ) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE runs
                SET finished_at = ?, status = ?, total_fetched = ?, total_scored = ?, total_sent = ?, note = ?
                WHERE run_id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    total_fetched,
                    total_scored,
                    total_sent,
                    note,
                    run_id,
                ),
            )
