"""Prepare the database and storage before the API starts.

    python -m scripts.migrate

1. Applies pending schema migrations (app/migrations.py).
2. Creates the storage bucket when MinIO is used.
3. Creates the first administrator from ADMIN_EMAIL / ADMIN_PASSWORD.
4. Creates the team accounts from seed/users.json with SEED_PASSWORD.
5. With SEED_DEMO=1, loads demo meetings from seed/demo (recordings and protocols).

Every step is idempotent, so it is safe to run on every start. docker compose runs it as
the `migrate` service before `backend`.
"""

import logging
import os
from pathlib import Path

from app.blobs import make_blob_store
from app.config import Settings
from app.seed import DEFAULT_SEED_FILE, bootstrap_admin, seed_demo_meetings, seed_users
from app.store import Store


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()
    store = Store(settings)
    applied = store.applied_migrations
    print(f"База данных ({store.backend}): применено миграций {len(applied)}" + (f": {', '.join(applied)}" if applied else ", схема актуальна"))
    blobs = make_blob_store(settings)
    blobs.prepare()
    print(f"Хранилище ({blobs.kind}) готово")
    admin = bootstrap_admin(store, settings)
    if admin:
        print(f"Создан администратор {admin['email']}")
    seed_file = Path(os.getenv("SEED_FILE") or DEFAULT_SEED_FILE)
    for user in seed_users(store, os.getenv("SEED_PASSWORD", ""), seed_file):
        print(f"Создана командная учётная запись {user['email']} ({user['role']})")
    if os.getenv("SEED_DEMO", "0").strip().lower() in {"1", "true", "yes"}:
        for meeting in seed_demo_meetings(store, blobs, os.getenv("SEED_DEMO_OWNER", "team@hattama.local")):
            print(f"Загружено демо-совещание «{meeting['title']}»")
    store.engine.dispose()


if __name__ == "__main__":
    main()
