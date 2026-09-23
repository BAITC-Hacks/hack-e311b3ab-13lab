"""Table definitions shared by the store and the migrations."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, MetaData, String, Table
from sqlalchemy.dialects.postgresql import JSONB


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


def meeting_columns(meeting):
    return {
        "id": meeting["id"],
        "version": meeting["version"],
        "status": meeting["status"],
        "created_by": meeting.get("created_by"),
        "created_at": meeting["created_at"],
        "body": meeting,
    }
