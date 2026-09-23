import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.blobs import LocalBlobStore, check_key
from app.security import hash_password, verify_password
from app.store import Store, audio_key, new_meeting
from tests.helpers import make_settings


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_legacy_sqlite_table_is_migrated(self):
        legacy = {"id": "old1", "title": "Старое", "meeting_date": "2026-09-01", "status": "ready", "created_at": "2026-09-01T10:00:00+00:00", "updated_at": "2026-09-01T10:00:00+00:00", "version": 3, "audio_file": "old1.mp3"}
        connection = sqlite3.connect(Path(self.directory.name) / "meetings.sqlite3")
        connection.execute("CREATE TABLE meetings (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        connection.execute("INSERT INTO meetings VALUES (?, ?)", ("old1", json.dumps(legacy)))
        connection.commit()
        connection.close()
        store = Store(self.settings)
        migrated = store.get("old1")
        self.assertEqual(migrated["title"], "Старое")
        self.assertIsNone(migrated["created_by"])
        self.assertEqual(audio_key(migrated), "audio/old1.mp3")
        self.assertEqual(store.update("old1", {"title": "Новое"}, expected_version=3)["version"], 4)
        store.engine.dispose()

    def test_versioned_updates(self):
        store = Store(self.settings)
        meeting = new_meeting("Тест", "2026-09-23", "audio/x.mp3")
        store.create(meeting)
        store.update(meeting["id"], lambda document: document.update(title="Изменено"))
        with self.assertRaises(ValueError):
            store.update(meeting["id"], {"title": "Устарело"}, expected_version=1)
        with self.assertRaises(KeyError):
            store.update("missing", {"title": "x"})
        self.assertEqual(store.get(meeting["id"])["title"], "Изменено")
        self.assertEqual(store.count_active(), 1)
        store.engine.dispose()

    def test_sessions_expire(self):
        store = Store(make_settings(self.directory.name, session_hours=0))
        user = store.create_user("a@example.kz", "A", "secretary", "long-enough-password")
        token, _ = store.create_session(user["id"])
        self.assertIsNone(store.session_user(token))
        store.engine.dispose()


class BlobAndSecurityTests(unittest.TestCase):
    def test_storage_keys_cannot_escape(self):
        for key in ("../secret", "audio/../../etc", "/abs", "audio//x", "", "a" * 501):
            with self.assertRaises(ValueError, msg=key):
                check_key(key)
        self.assertEqual(check_key("protocols/abc/v2.pdf"), "protocols/abc/v2.pdf")

    def test_local_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            blobs = LocalBlobStore(Path(directory))
            source = Path(directory) / "upload.tmp"
            source.write_bytes(b"data")
            blobs.put_file("audio/x.mp3", source)
            self.assertFalse(source.exists())
            self.assertEqual(b"".join(blobs.open_stream("audio/x.mp3")), b"data")
            blobs.put_bytes("protocols/m/v2.docx", b"doc")
            blobs.delete_prefix("protocols/m")
            self.assertFalse(blobs.exists("protocols/m/v2.docx"))

    def test_password_hashing(self):
        encoded = hash_password("long-enough-password")
        self.assertTrue(verify_password("long-enough-password", encoded))
        self.assertFalse(verify_password("wrong", encoded))
        self.assertFalse(verify_password("x", "not-a-hash"))


if __name__ == "__main__":
    unittest.main()
