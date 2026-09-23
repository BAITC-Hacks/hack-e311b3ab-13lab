import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "meetings.sqlite3"
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY, body TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, meeting):
        with self.connect() as connection:
            connection.execute("INSERT INTO meetings VALUES (?, ?)", (meeting["id"], json.dumps(meeting, ensure_ascii=False)))

    def get(self, meeting_id):
        with self.connect() as connection:
            row = connection.execute("SELECT body FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT body FROM meetings ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def update(self, meeting_id, changes, expected_version=None):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT body FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            if not row:
                raise KeyError(meeting_id)
            meeting = json.loads(row[0])
            if expected_version is not None and expected_version != meeting["version"]:
                raise ValueError("Version conflict")
            meeting.update(changes)
            meeting["version"] += 1
            meeting["updated_at"] = now()
            connection.execute("UPDATE meetings SET body = ? WHERE id = ?", (json.dumps(meeting, ensure_ascii=False), meeting_id))
        return meeting
