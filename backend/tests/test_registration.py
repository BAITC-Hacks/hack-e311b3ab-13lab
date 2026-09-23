import tempfile
import unittest

from sqlalchemy import create_engine, inspect, text

from app.migrations import migrate
from app.store import database_url
from tests.helpers import PASSWORD, AppTestCase, make_settings

NEW_USER = {"email": "new@example.kz", "name": "Новый сотрудник", "password": "long-enough-password"}


class ApprovalRegistrationTests(AppTestCase):
    def test_registration_waits_for_approval(self):
        self.assertEqual(self.client.get("/api/auth/registration").json(), {"mode": "approval"})
        response = self.client.post("/api/auth/register", json=NEW_USER)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"status": "pending"})
        self.assertEqual(self.client.post("/api/auth/register", json=NEW_USER).status_code, 409)
        login = {"email": NEW_USER["email"], "password": NEW_USER["password"]}
        self.assertEqual(self.client.post("/api/auth/login", json=login).status_code, 403)
        self.assertEqual(self.client.post("/api/auth/login", json=login | {"password": "wrong-password"}).status_code, 401)

        overview = self.get("/api/admin/overview", "admin").json()
        pending = overview["pending_registrations"]
        self.assertEqual([item["email"] for item in pending], [NEW_USER["email"]])
        self.assertEqual(overview["users"]["pending"], 1)

        path = f"/api/admin/registrations/{pending[0]['id']}/approve"
        self.assertEqual(self.client.post(path, headers=self.auth("secretary"), json={"role": "chair"}).status_code, 403)
        approved = self.client.post(path, headers=self.auth("admin"), json={"role": "chair"})
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["role"], "chair")
        self.assertEqual(self.client.post(path, headers=self.auth("admin"), json={"role": "chair"}).status_code, 404)
        session = self.client.post("/api/auth/login", json=login)
        self.assertEqual(session.status_code, 200)
        self.assertIsNotNone(self.get("/api/users", "admin").json() and self.store.get_user(pending[0]["id"])["last_login_at"])

    def test_rejected_registration_is_removed(self):
        self.client.post("/api/auth/register", json=NEW_USER)
        user_id = self.store.pending_users()[0]["id"]
        self.assertEqual(self.client.delete(f"/api/admin/registrations/{user_id}", headers=self.auth("admin")).status_code, 204)
        self.assertIsNone(self.store.get_user(user_id))
        existing = self.users["secretary"]["id"]
        self.assertEqual(self.client.delete(f"/api/admin/registrations/{existing}", headers=self.auth("admin")).status_code, 404)
        self.assertIsNotNone(self.store.get_user(existing))
        actions = {entry["action"] for entry in self.get("/api/audit", "admin").json()}
        self.assertTrue({"user_registered", "registration_rejected"} <= actions)

    def test_registration_cannot_choose_role_and_is_throttled(self):
        self.assertEqual(self.client.post("/api/auth/register", json=NEW_USER | {"role": "admin"}).status_code, 422)
        for index in range(4):
            self.client.post("/api/auth/register", json=NEW_USER | {"email": f"user{index}@example.kz"})
        self.assertEqual(self.client.post("/api/auth/register", json=NEW_USER | {"email": "late@example.kz"}).status_code, 201)
        self.assertEqual(self.client.post("/api/auth/register", json=NEW_USER | {"email": "blocked@example.kz"}).status_code, 429)

    def test_overview_reports_system(self):
        self.ready_meeting()
        overview = self.get("/api/admin/overview", "admin").json()
        self.assertEqual(overview["system"]["database"], "sqlite")
        self.assertEqual(overview["system"]["storage"], "local")
        self.assertEqual([item["id"] for item in overview["system"]["migrations"]], ["0001_initial_schema", "0002_user_registration"])
        self.assertEqual(overview["meetings"]["by_status"], {"ready": 1})
        self.assertEqual(overview["users"]["by_role"]["participant"], 2)
        self.assertTrue(overview["recent_activity"])
        self.assertEqual(self.get("/api/admin/overview", "auditor").status_code, 403)

    def test_activating_pending_user_clears_pending(self):
        self.client.post("/api/auth/register", json=NEW_USER)
        user_id = self.store.pending_users()[0]["id"]
        self.client.patch(f"/api/users/{user_id}", headers=self.auth("admin"), json={"active": True})
        self.assertFalse(self.store.get_user(user_id)["pending"])
        self.assertEqual(self.client.post("/api/auth/login", json={"email": NEW_USER["email"], "password": NEW_USER["password"]}).status_code, 200)


class OpenRegistrationTests(AppTestCase):
    settings_overrides = {"registration_mode": "open"}

    def test_open_registration_signs_in_as_participant(self):
        response = self.client.post("/api/auth/register", json=NEW_USER).json()
        self.assertEqual(response["status"], "active")
        self.assertEqual(response["user"]["role"], "participant")
        me = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {response['token']}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(self.client.get("/api/meetings", headers={"Authorization": f"Bearer {response['token']}"}).json(), [])


class ClosedRegistrationTests(AppTestCase):
    settings_overrides = {"registration_mode": "closed"}

    def test_closed_registration(self):
        self.assertEqual(self.client.get("/api/auth/registration").json(), {"mode": "closed"})
        self.assertEqual(self.client.post("/api/auth/register", json=NEW_USER).status_code, 403)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "secretary@example.kz", "password": PASSWORD}).status_code, 200)


class RegistrationMigrationTests(unittest.TestCase):
    def test_columns_added_to_existing_users_table(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(database_url(make_settings(directory)))
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE users (id VARCHAR(32) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE, name VARCHAR(200) NOT NULL, role VARCHAR(20) NOT NULL, password_hash VARCHAR(300) NOT NULL, active BOOLEAN NOT NULL, created_at VARCHAR(40) NOT NULL)"))
                connection.execute(text("INSERT INTO users VALUES ('u1', 'old@example.kz', 'Old', 'secretary', 'x', 1, '2026-09-01')"))
                connection.execute(text("CREATE TABLE schema_migrations (id VARCHAR(100) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)"))
                connection.execute(text("INSERT INTO schema_migrations VALUES ('0001_initial_schema', '2026-09-01')"))
            self.assertEqual(migrate(engine), ["0002_user_registration"])
            self.assertTrue({"pending", "last_login_at"} <= {column["name"] for column in inspect(engine).get_columns("users")})
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT pending FROM users")).scalar_one(), 0)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
