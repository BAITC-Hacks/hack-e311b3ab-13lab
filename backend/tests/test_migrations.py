import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, select

from app.migrations import MIGRATIONS, migrate, schema_migrations
from app.seed import bootstrap_admin, seed_users
from app.store import Store
from tests.helpers import make_settings


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = make_settings(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_migrations_are_recorded_and_idempotent(self):
        store = Store(self.settings)
        self.assertEqual(store.applied_migrations, [migration_id for migration_id, _ in MIGRATIONS])
        self.assertEqual(migrate(store.engine), [])
        with store.engine.connect() as connection:
            recorded = connection.execute(select(schema_migrations.c.id)).scalars().all()
        self.assertEqual(sorted(recorded), sorted(migration_id for migration_id, _ in MIGRATIONS))
        self.assertEqual(Store(self.settings).applied_migrations, [])
        store.engine.dispose()

    def test_database_created_before_migrations_is_adopted(self):
        store = Store(self.settings)
        with store.engine.begin() as connection:
            schema_migrations.drop(connection)
        adopted = Store(self.settings)
        self.assertEqual(adopted.applied_migrations, [migration_id for migration_id, _ in MIGRATIONS])
        self.assertIn("users", inspect(adopted.engine).get_table_names())
        store.engine.dispose()
        adopted.engine.dispose()


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(make_settings(self.directory.name))
        self.seed_file = Path(self.directory.name) / "users.json"
        self.seed_file.write_text(json.dumps({"users": [{"email": "Team@Example.kz", "name": "Команда", "role": "secretary"}]}), encoding="utf-8")

    def tearDown(self):
        self.store.engine.dispose()
        self.directory.cleanup()

    def test_seed_is_idempotent(self):
        self.assertEqual([user["email"] for user in seed_users(self.store, "team-password-1", self.seed_file)], ["team@example.kz"])
        self.assertEqual(seed_users(self.store, "another-password", self.seed_file), [])
        _, password_hash = self.store.user_credentials("team@example.kz")
        from app.security import verify_password

        self.assertTrue(verify_password("team-password-1", password_hash))

    def test_seed_skipped_without_password(self):
        self.assertEqual(seed_users(self.store, "", self.seed_file), [])
        self.assertIsNone(self.store.user_credentials("team@example.kz"))

    def test_repository_seed_file_is_valid(self):
        from app.seed import DEFAULT_SEED_FILE

        created = seed_users(self.store, "team-password-1", DEFAULT_SEED_FILE)
        self.assertEqual([user["role"] for user in created], ["secretary"])

    def test_demo_meetings_load_once(self):
        from app.blobs import LocalBlobStore
        from app.seed import DEMO_DIR, seed_demo_meetings

        blobs = LocalBlobStore(Path(self.directory.name) / "blobs")
        seed_users(self.store, "team-password-1", self.seed_file)
        loaded = seed_demo_meetings(self.store, blobs, "team@example.kz")
        self.assertEqual({meeting["title"] for meeting in loaded}, {"Демо: переговорная, совещание 1", "ozimiz", "test11"})
        owner = self.store.user_credentials("team@example.kz")[0]["id"]
        for meeting in loaded:
            stored = self.store.get(meeting["id"])
            self.assertEqual(stored["created_by"], owner)
            self.assertEqual(stored["status"], "ready")
            self.assertTrue(blobs.exists(stored["audio_key"]))
        self.assertEqual(seed_demo_meetings(self.store, blobs, "team@example.kz"), [])
        self.assertTrue((DEMO_DIR / "ozimiz.reference.txt").is_file())

    def test_bootstrap_admin_once(self):
        settings = make_settings(self.directory.name, admin_email="admin@example.kz", admin_password="admin-password-1")
        self.assertIsNotNone(bootstrap_admin(self.store, settings))
        self.assertIsNone(bootstrap_admin(self.store, settings))


if __name__ == "__main__":
    unittest.main()
