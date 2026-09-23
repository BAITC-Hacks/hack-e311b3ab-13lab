"""Relational storage for meetings, users, sessions and the audit log.

PostgreSQL is used when DATABASE_URL is set, otherwise SQLite in DATA_DIR. Each meeting is
still one JSON document (JSONB on PostgreSQL); status, version, creator and creation time are
also kept as columns for filtering and optimistic concurrency.
"""

import json
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    event,
    func,
    insert,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from app.models import ACTIVE_STATUSES
from app.security import hash_password, new_token, token_digest


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


metadata = MetaData()
Document = JSON().with_variant(JSONB(), "postgresql")

users = Table(
    "users",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("name", String(200), nullable=False),
    Column("role", String(20), nullable=False),
    Column("password_hash", String(300), nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", String(40), nullable=False),
)

sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("expires_at", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
)

meetings = Table(
    "meetings",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("version", Integer, nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("created_by", String(32), nullable=True),
    Column("created_at", String(40), nullable=False, index=True),
    Column("body", Document, nullable=False),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", String(40), nullable=False, index=True),
    Column("user_id", String(32), nullable=True),
    Column("user_email", String(254), nullable=True),
    Column("action", String(60), nullable=False),
    Column("meeting_id", String(32), nullable=True, index=True),
    Column("detail", Document, nullable=False),
)

PUBLIC_USER_FIELDS = ("id", "email", "name", "role", "active", "created_at")


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


def new_meeting(title, meeting_date, audio_key, created_by=None, chair_id=None):
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
    }


def audio_key(meeting):
    # Meetings created before object storage only have `audio_file` inside DATA_DIR/audio.
    return meeting.get("audio_key") or f"audio/{meeting['audio_file']}"


def _columns(meeting):
    return {
        "id": meeting["id"],
        "version": meeting["version"],
        "status": meeting["status"],
        "created_by": meeting.get("created_by"),
        "created_at": meeting["created_at"],
        "body": meeting,
    }


def _public_user(row):
    return {field: row._mapping[field] for field in PUBLIC_USER_FIELDS}


class Store:
    def __init__(self, settings):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine = make_engine(settings)
        self.backend = self.engine.dialect.name
        self.session_seconds = int(settings.session_hours * 3600)
        with self.engine.begin() as connection:
            self._migrate_legacy(connection)
            metadata.create_all(connection)

    def _migrate_legacy(self, connection):
        """Move rows from the MVP table `meetings(id, body)` into the new schema."""
        inspector = inspect(connection)
        if "meetings" not in inspector.get_table_names():
            return
        if "version" in {column["name"] for column in inspector.get_columns("meetings")}:
            return
        connection.execute(text("ALTER TABLE meetings RENAME TO meetings_legacy"))
        rows = connection.execute(text("SELECT body FROM meetings_legacy")).fetchall()
        metadata.create_all(connection)
        for (body,) in rows:
            meeting = json.loads(body) if isinstance(body, str) else body
            meeting.setdefault("created_by", None)
            meeting.setdefault("chair_id", None)
            meeting.setdefault("participant_ids", [])
            meeting.setdefault("approvals", [])
            connection.execute(insert(meetings).values(**_columns(meeting)))

    # Meetings

    def create(self, meeting):
        with self.engine.begin() as connection:
            connection.execute(insert(meetings).values(**_columns(meeting)))

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

    def create_user(self, email, name, role, password):
        user = {"id": uuid.uuid4().hex, "email": email.strip().lower(), "name": name.strip(), "role": str(role), "active": True, "created_at": now()}
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

    def update_user(self, user_id, name=None, role=None, active=None, password=None):
        values = {}
        if name is not None:
            values["name"] = name.strip()
        if role is not None:
            values["role"] = str(role)
        if active is not None:
            values["active"] = active
        if password is not None:
            values["password_hash"] = hash_password(password)
        with self.engine.begin() as connection:
            if values:
                connection.execute(update(users).where(users.c.id == user_id).values(**values))
            if password is not None or active is False:
                connection.execute(delete(sessions).where(sessions.c.user_id == user_id))
        return self.get_user(user_id)

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
