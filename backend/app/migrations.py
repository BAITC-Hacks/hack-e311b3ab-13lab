"""Versioned schema migrations.

Each migration runs once, in order, inside one transaction, and is recorded in
`schema_migrations`. Steps inspect the live schema before changing it, so they are safe
on databases that were created before this table existed. To change the schema, update
`app/schema.py` and append a new step here; never edit a step that has shipped.

Run them explicitly with `python -m scripts.migrate`; the Store also applies them on start.
"""

import json

from sqlalchemy import Column, String, Table, insert, inspect, select, text

from app.schema import meeting_columns, meetings, metadata, now

schema_migrations = Table(
    "schema_migrations",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("applied_at", String(40), nullable=False),
)

MIGRATION_LOCK_ID = 4_247_113  # arbitrary constant for pg_advisory_xact_lock


def _columns(connection, table):
    return {column["name"] for column in inspect(connection).get_columns(table)}


def initial_schema(connection):
    """Create the base tables. Converts the MVP SQLite table `meetings(id, body)` first."""
    if "meetings" in inspect(connection).get_table_names() and "version" not in _columns(connection, "meetings"):
        connection.execute(text("ALTER TABLE meetings RENAME TO meetings_legacy"))
        rows = connection.execute(text("SELECT body FROM meetings_legacy")).fetchall()
        metadata.create_all(connection, tables=[meetings])
        for (body,) in rows:
            meeting = json.loads(body) if isinstance(body, str) else body
            for field, default in (("created_by", None), ("chair_id", None), ("participant_ids", []), ("approvals", [])):
                meeting.setdefault(field, default)
            connection.execute(insert(meetings).values(**meeting_columns(meeting)))
    metadata.create_all(connection, tables=[table for table in metadata.sorted_tables if table.name != "schema_migrations"])


MIGRATIONS = [
    ("0001_initial_schema", initial_schema),
]


def migrate(engine):
    """Apply pending migrations and return the ids that were applied in this call."""
    applied_now = []
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": MIGRATION_LOCK_ID})
        schema_migrations.create(connection, checkfirst=True)
        done = set(connection.execute(select(schema_migrations.c.id)).scalars())
        for migration_id, step in MIGRATIONS:
            if migration_id in done:
                continue
            step(connection)
            connection.execute(insert(schema_migrations).values(id=migration_id, applied_at=now()))
            applied_now.append(migration_id)
    return applied_now
