"""Relational storage for meetings, users, sessions and the audit log.

PostgreSQL is used when DATABASE_URL is set, otherwise SQLite in DATA_DIR. Each meeting is
still one JSON document (JSONB on PostgreSQL); status, version, creator and creation time are
also kept as columns for filtering and optimistic concurrency.
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, delete, event, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.migrations import migrate
from app.models import ACTIVE_STATUSES
from app.schema import PUBLIC_USER_FIELDS, audit_log, meeting_columns, meetings, metadata, now, sessions, users
from app.security import hash_password, new_token, token_digest

__all__ = ["Store", "audio_key", "database_url", "make_engine", "metadata", "new_meeting", "now"]


def database_url(settings):
    url = settings.database_url
    if not url:
        return f"sqlite:///{(settings.data_dir / 'meetings.sqlite3').resolve()}"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(settings):
    url = database_url(settings)
    serializer = lambda value: json.dumps(value, ensure_ascii=False)  # noqa: E731
    if url.startswith("sqlite"):
        engine = create_engine(url, json_serializer=serializer, connect_args={"timeout": 15, "check_same_thread": False})

        @event.listens_for(engine, "connect")
        def sqlite_pragmas(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, json_serializer=serializer, pool_pre_ping=True)


def new_meeting(title, meeting_date, audio_key, created_by=None, chair_id=None, source=None):
    timestamp = now()
    return {
        "id": uuid.uuid4().hex,
        "title": title,
        "meeting_date": meeting_date,
        "status": "queued",
        "created_at": timestamp,
        "updated_at": timestamp,
        "version": 1,
        "audio_key": audio_key,
        "transcript": "",
        "segments": [],
        "analysis": None,
        "speaker_names": {},
        "error": None,
        "recording_consent": True,
        "created_by": created_by,
        "chair_id": chair_id,
        "participant_ids": [],
        "approved_at": None,
        "approved_by": None,
        "approvals": [],
        "source": source or {"type": "upload"},
    }


def audio_key(meeting):
    """Storage key of the recording, or None when the meeting never got audio (e.g. a
    live session that ended before any sound). Old meetings only have `audio_file`."""
    if meeting.get("audio_key"):
        return meeting["audio_key"]
    return f"audio/{meeting['audio_file']}" if meeting.get("audio_file") else None


def _public_user(row):
    return {field: row._mapping[field] for field in PUBLIC_USER_FIELDS}


class Store:
    def __init__(self, settings):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine = make_engine(settings)
        self.backend = self.engine.dialect.name
        self.session_seconds = int(settings.session_hours * 3600)
        self.applied_migrations = migrate(self.engine)

    # Meetings

    def create(self, meeting):
        with self.engine.begin() as connection:
            connection.execute(insert(meetings).values(**meeting_columns(meeting)))

    def get(self, meeting_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(meetings.c.body).where(meetings.c.id == meeting_id)).first()
        return row.body if row else None

    def all(self):
        with self.engine.connect() as connection:
            rows = connection.execute(select(meetings.c.body).order_by(meetings.c.created_at.desc(), meetings.c.id.desc())).fetchall()
        return [row.body for row in rows]

    def count_active(self):
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(meetings).where(meetings.c.status.in_(ACTIVE_STATUSES))).scalar_one()

    def mark_interrupted(self, message):
        with self.engine.connect() as connection:
            ids = connection.execute(select(meetings.c.id).where(meetings.c.status.in_(ACTIVE_STATUSES))).scalars().all()
        for meeting_id in ids:
            self.update(meeting_id, {"status": "failed", "error": message})

    def update(self, meeting_id, changes, expected_version=None):
        """Apply `changes` (a dict, or a function that mutates the document) atomically.

        The UPDATE only succeeds if the version is unchanged since the read, so concurrent
        writers never overwrite each other. With `expected_version` a mismatch raises
        ValueError; without it the read-modify-write is retried.
        """
        for _attempt in range(20):
            with self.engine.begin() as connection:
                row = connection.execute(select(meetings.c.body, meetings.c.version).where(meetings.c.id == meeting_id)).first()
                if not row:
                    raise KeyError(meeting_id)
                meeting, version = dict(row.body), row.version
                if expected_version is not None and expected_version != version:
                    raise ValueError("Version conflict")
                if callable(changes):
                    changes(meeting)
                else:
                    meeting.update(changes)
                meeting["version"] = version + 1
                meeting["updated_at"] = now()
                result = connection.execute(
                    update(meetings)
                    .where(meetings.c.id == meeting_id, meetings.c.version == version)
                    .values(body=meeting, version=version + 1, status=meeting["status"])
                )
                if result.rowcount == 1:
                    return meeting
            if expected_version is not None:
                raise ValueError("Version conflict")
        raise RuntimeError("Не удалось сохранить изменения: слишком много одновременных правок")

    def delete(self, meeting_id):
        with self.engine.begin() as connection:
            connection.execute(delete(meetings).where(meetings.c.id == meeting_id))

    # Users

    def count_users(self, role=None):
        query = select(func.count()).select_from(users).where(users.c.active.is_(True))
        if role:
            query = query.where(users.c.role == str(role))
        with self.engine.connect() as connection:
            return connection.execute(query).scalar_one()

    def create_user(self, email, name, role, password, pending=False):
        user = {"id": uuid.uuid4().hex, "email": email.strip().lower(), "name": name.strip(), "role": str(role), "active": not pending, "created_at": now(), "pending": pending, "last_login_at": None}
        try:
            with self.engine.begin() as connection:
                connection.execute(insert(users).values(**user, password_hash=hash_password(password)))
        except IntegrityError as error:
            raise ValueError("Email already registered") from error
        return user

    def get_user(self, user_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(*[users.c[field] for field in PUBLIC_USER_FIELDS]).where(users.c.id == user_id)).first()
        return _public_user(row) if row else None

    def user_credentials(self, email):
        with self.engine.connect() as connection:
            row = connection.execute(select(users).where(users.c.email == email.strip().lower())).first()
        return (_public_user(row), row.password_hash) if row else None

    def list_users(self):
        with self.engine.connect() as connection:
            rows = connection.execute(select(*[users.c[field] for field in PUBLIC_USER_FIELDS]).order_by(users.c.name, users.c.email)).fetchall()
        return [_public_user(row) for row in rows]

    def user_names(self):
        with self.engine.connect() as connection:
            return dict(connection.execute(select(users.c.id, users.c.name)).fetchall())

    def pending_users(self):
        with self.engine.connect() as connection:
            rows = connection.execute(select(*[users.c[field] for field in PUBLIC_USER_FIELDS]).where(users.c.pending.is_(True)).order_by(users.c.created_at)).fetchall()
        return [_public_user(row) for row in rows]

    def approve_user(self, user_id, role):
        with self.engine.begin() as connection:
            result = connection.execute(update(users).where(users.c.id == user_id, users.c.pending.is_(True)).values(pending=False, active=True, role=str(role)))
        return self.get_user(user_id) if result.rowcount else None

    def reject_user(self, user_id):
        """Delete a pending registration. Accounts that were ever approved are never deleted."""
        with self.engine.begin() as connection:
            row = connection.execute(select(users.c.email).where(users.c.id == user_id, users.c.pending.is_(True))).first()
            if row:
                connection.execute(delete(users).where(users.c.id == user_id))
        return row.email if row else None

    def record_login(self, user_id):
        with self.engine.begin() as connection:
            connection.execute(update(users).where(users.c.id == user_id).values(last_login_at=now()))

    def user_counts(self):
        with self.engine.connect() as connection:
            rows = connection.execute(select(users.c.role, users.c.active, users.c.pending, func.count()).group_by(users.c.role, users.c.active, users.c.pending)).fetchall()
        return [{"role": role, "active": bool(active), "pending": bool(pending), "count": count} for role, active, pending, count in rows]

    def meeting_counts(self):
        with self.engine.connect() as connection:
            return dict(connection.execute(select(meetings.c.status, func.count()).group_by(meetings.c.status)).fetchall())

    def dashboard_metrics(self, at=None):
        """Only aggregate metadata leaves this method; no transcript, titles or owners."""
        zone = ZoneInfo("Asia/Almaty")
        today = (at or datetime.now(zone)).astimezone(zone).date()
        daily = {(today - timedelta(days=offset)).isoformat(): 0 for offset in range(29, -1, -1)}
        actions = {"total": 0, "open": 0, "in_progress": 0, "done": 0, "needs_review": 0}
        with self.engine.connect() as connection:
            # Extract just the action array, never the audio or transcript.
            rows = connection.execute(select(meetings.c.created_at, meetings.c.status, meetings.c.body["analysis"]["actions"])).fetchall()
        for created_at, status, items in rows:
            created = datetime.fromisoformat(created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=ZoneInfo("UTC"))
            day = created.astimezone(zone).date().isoformat()
            if day in daily:
                daily[day] += 1
            if status not in {"ready", "approved"}:
                continue
            for item in items or []:
                actions["total"] += 1
                state = item.get("status", "open")
                if state in {"open", "in_progress", "done"}:
                    actions[state] += 1
                if item.get("needs_review", False):
                    actions["needs_review"] += 1
        return {"timezone": "Asia/Almaty", "daily_uploads": [{"date": day, "count": count} for day, count in daily.items()], "actions": actions}

    def update_user(self, user_id, name=None, role=None, active=None, password=None):
        values = {}
        if name is not None:
            values["name"] = name.strip()
        if role is not None:
            values["role"] = str(role)
        if active is not None:
            values["active"] = active
            if active:
                values["pending"] = False
        if password is not None:
            values["password_hash"] = hash_password(password)
        with self.engine.begin() as connection:
            if values:
                connection.execute(update(users).where(users.c.id == user_id).values(**values))
            if password is not None or active is False:
                connection.execute(delete(sessions).where(sessions.c.user_id == user_id))
        return self.get_user(user_id)

    def migration_history(self):
        from app.migrations import schema_migrations

        with self.engine.connect() as connection:
            rows = connection.execute(select(schema_migrations.c.id, schema_migrations.c.applied_at).order_by(schema_migrations.c.id)).fetchall()
        return [{"id": migration_id, "applied_at": applied_at} for migration_id, applied_at in rows]

    # Sessions

    def create_session(self, user_id):
        token = new_token()
        expires_at = int(time.time()) + self.session_seconds
        with self.engine.begin() as connection:
            connection.execute(delete(sessions).where(sessions.c.expires_at <= int(time.time())))
            connection.execute(insert(sessions).values(token_hash=token_digest(token), user_id=user_id, expires_at=expires_at, created_at=now()))
        return token, expires_at

    def session_user(self, token):
        query = (
            select(*[users.c[field] for field in PUBLIC_USER_FIELDS])
            .join(sessions, sessions.c.user_id == users.c.id)
            .where(sessions.c.token_hash == token_digest(token), sessions.c.expires_at > int(time.time()), users.c.active.is_(True))
        )
        with self.engine.connect() as connection:
            row = connection.execute(query).first()
        return _public_user(row) if row else None

    def delete_session(self, token):
        with self.engine.begin() as connection:
            connection.execute(delete(sessions).where(sessions.c.token_hash == token_digest(token)))

    # Audit log

    def audit(self, action, user=None, meeting_id=None, **detail):
        with self.engine.begin() as connection:
            connection.execute(
                insert(audit_log).values(
                    at=now(),
                    user_id=user["id"] if user else None,
                    user_email=user["email"] if user else detail.pop("email", None),
                    action=action,
                    meeting_id=meeting_id,
                    detail=detail,
                )
            )

    def audit_entries(self, meeting_id=None, limit=200):
        query = select(audit_log).order_by(audit_log.c.id.desc()).limit(limit)
        if meeting_id:
            query = query.where(audit_log.c.meeting_id == meeting_id)
        with self.engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(query).fetchall()]
