"""Idempotent creation of the first administrator and the shared team accounts."""

import json
import logging
from pathlib import Path

from app.rbac import Role
from app.security import MIN_PASSWORD_LENGTH

logger = logging.getLogger("hattama")
DEFAULT_SEED_FILE = Path(__file__).resolve().parents[1] / "seed" / "users.json"


def bootstrap_admin(store, settings):
    """Create the administrator from ADMIN_EMAIL / ADMIN_PASSWORD if no active admin exists."""
    if store.count_users(Role.ADMIN):
        return None
    if not (settings.admin_email and settings.admin_password):
        logger.warning("Нет активного администратора. Задайте ADMIN_EMAIL и ADMIN_PASSWORD или выполните python -m scripts.create_user")
        return None
    if store.user_credentials(settings.admin_email):
        logger.warning("Пользователь %s уже существует, но не является активным администратором", settings.admin_email)
        return None
    user = store.create_user(settings.admin_email, settings.admin_name, Role.ADMIN, settings.admin_password)
    store.audit("user_created", email=user["email"], role=user["role"], source="bootstrap")
    logger.warning("Создан администратор %s из ADMIN_EMAIL/ADMIN_PASSWORD", user["email"])
    return user


def seed_users(store, password, path=DEFAULT_SEED_FILE):
    """Create every account listed in the seed file that does not exist yet."""
    entries = json.loads(Path(path).read_text(encoding="utf-8")).get("users", [])
    if not entries:
        return []
    if len(password) < MIN_PASSWORD_LENGTH:
        logger.warning("SEED_PASSWORD не задан или короче %s символов: командные учётные записи не созданы", MIN_PASSWORD_LENGTH)
        return []
    created = []
    for entry in entries:
        if store.user_credentials(entry["email"]):
            continue
        user = store.create_user(entry["email"], entry["name"], Role(entry["role"]), password)
        store.audit("user_created", email=user["email"], role=user["role"], source="seed")
        created.append(user)
    return created


DEMO_DIR = Path(__file__).resolve().parents[1] / "seed" / "demo"


def seed_demo_meetings(store, blobs, owner_email, directory=DEMO_DIR):
    """Load demo meetings (with their recordings) that are not in the database yet."""
    manifest = Path(directory) / "meetings.json"
    if not manifest.is_file():
        return []
    owner = store.user_credentials(owner_email)
    owner_id = owner[0]["id"] if owner else None
    loaded = []
    for meeting in json.loads(manifest.read_text(encoding="utf-8")).get("meetings", []):
        if store.get(meeting["id"]):
            continue
        key = meeting.get("audio_key")
        if key:
            audio = Path(directory) / "audio" / Path(key).name
            if not audio.is_file():
                logger.warning("Нет записи для демо-совещания %s", meeting["title"])
                continue
            blobs.put_bytes(key, audio.read_bytes())
        store.create(meeting | {"created_by": owner_id})
        store.audit("meeting_created", meeting_id=meeting["id"], email=owner_email, title=meeting["title"], source="demo")
        loaded.append(meeting)
    return loaded
