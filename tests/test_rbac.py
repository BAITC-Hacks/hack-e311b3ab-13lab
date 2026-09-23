import unittest

from app.rbac import Role, meeting_permissions
from tests.helpers import PASSWORD, AppTestCase


class PermissionFunctionTests(unittest.TestCase):
    def test_secretary_has_everything_and_admin_only_metadata(self):
        meeting = {"status": "ready", "created_by": "x", "participant_ids": []}
        self.assertIn("delete", meeting_permissions({"id": "s", "role": Role.SECRETARY}, meeting))
        self.assertEqual(meeting_permissions({"id": "a", "role": Role.ADMIN}, meeting), {"view", "delete"})
        self.assertEqual(meeting_permissions({"id": "u", "role": Role.AUDITOR}, meeting), {"view"})
        self.assertEqual(meeting_permissions({"id": "p", "role": Role.PARTICIPANT}, meeting), set())


class RoleAccessTests(AppTestCase):
    def test_only_secretary_and_chair_can_upload(self):
        for name in ("admin", "auditor", "participant"):
            self.assertEqual(self.upload(as_user=name).status_code, 403, name)
        response = self.upload(as_user="chair")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["chair_id"], self.users["chair"]["id"])

    def test_admin_and_auditor_see_metadata_only(self):
        meeting = self.ready_meeting()
        for name in ("admin", "auditor"):
            detail = self.get(f"/api/meetings/{meeting['id']}", name).json()
            self.assertEqual(detail["title"], "Тест")
            self.assertNotIn("transcript", detail)
            self.assertNotIn("analysis", detail)
            self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/audio", name).status_code, 403)
            self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/export/md", name).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/meetings/{meeting['id']}", headers=self.auth("auditor")).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/meetings/{meeting['id']}", headers=self.auth("admin")).status_code, 204)

    def test_participant_sees_only_approved_meetings(self):
        meeting = self.ready_meeting()
        response = self.client.put(f"/api/meetings/{meeting['id']}/people", headers=self.auth("secretary"), json={"participant_ids": [self.users["participant"]["id"]]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}", "participant").status_code, 404)
        self.assertEqual(self.get("/api/meetings", "participant").json(), [])
        self.approve(response.json() | {"version": response.json()["version"]})
        detail = self.get(f"/api/meetings/{meeting['id']}", "participant").json()
        self.assertEqual(detail["analysis"]["actions"][0]["owner"], "Айжан")
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/export/md", "participant").status_code, 200)
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/export/json", "participant").status_code, 403)
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/audio", "participant").status_code, 403)
        self.assertEqual(self.review(detail, as_user="participant").status_code, 403)
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}", "outsider").status_code, 404)

    def test_chair_only_manages_own_meetings(self):
        meeting = self.ready_meeting()
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}", "chair").status_code, 404)
        response = self.client.put(f"/api/meetings/{meeting['id']}/people", headers=self.auth("secretary"), json={"chair_id": self.users["chair"]["id"]})
        self.assertEqual(response.status_code, 200)
        detail = self.get(f"/api/meetings/{meeting['id']}", "chair").json()
        self.assertIn("approve", detail["permissions"])
        self.assertNotIn("delete", detail["permissions"])
        self.assertEqual(self.review(detail, as_user="chair").status_code, 200)

    def test_chair_must_have_chair_role(self):
        meeting = self.ready_meeting()
        response = self.client.put(f"/api/meetings/{meeting['id']}/people", headers=self.auth("secretary"), json={"chair_id": self.users["participant"]["id"]})
        self.assertEqual(response.status_code, 422)
        response = self.client.put(f"/api/meetings/{meeting['id']}/people", headers=self.auth("secretary"), json={"participant_ids": ["missing"]})
        self.assertEqual(response.status_code, 422)


class WorkflowTests(AppTestCase):
    def test_approval_locks_edits_until_reopened(self):
        meeting = self.ready_meeting()
        stale = self.client.post(f"/api/meetings/{meeting['id']}/approve", headers=self.auth("secretary"), json={"version": meeting["version"] - 1})
        self.assertEqual(stale.status_code, 409)
        approved = self.approve(meeting)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approved_by"], self.users["secretary"]["id"])
        self.assertEqual(len(approved["approvals"]), 1)
        self.assertEqual(self.review(approved).status_code, 409)
        self.assertIn("Протокол утверждён", self.get(f"/api/meetings/{meeting['id']}/export/md", "secretary").text)
        reopened = self.client.post(f"/api/meetings/{meeting['id']}/reopen", headers=self.auth("secretary")).json()
        self.assertEqual(reopened["status"], "ready")
        self.assertEqual(self.review(reopened).status_code, 200)

    def test_assignee_updates_only_own_action(self):
        meeting = self.ready_meeting()
        meeting["analysis"]["actions"][0]["assignee_id"] = self.users["participant"]["id"]
        saved = self.review(meeting)
        self.assertEqual(saved.status_code, 200, saved.text)
        action_id = saved.json()["analysis"]["actions"][0]["id"]
        self.assertEqual(self.get("/api/me/actions", "participant").json(), [])
        approved = self.approve(saved.json())
        tasks = self.get("/api/me/actions", "participant").json()
        self.assertEqual([task["action"]["id"] for task in tasks], [action_id])
        self.assertIn(self.users["participant"]["id"], approved["people"])
        path = f"/api/meetings/{meeting['id']}/actions/{action_id}"
        self.assertEqual(self.client.patch(path, headers=self.auth("participant"), json={"status": "in_progress"}).status_code, 200)
        self.assertEqual(self.client.patch(path, headers=self.auth("outsider"), json={"status": "done"}).status_code, 404)
        self.assertEqual(self.client.patch(f"/api/meetings/{meeting['id']}/actions/missing", headers=self.auth("participant"), json={"status": "done"}).status_code, 404)
        self.assertEqual(self.client.patch(path, headers=self.auth("participant"), json={"status": "cancelled"}).status_code, 422)
        detail = self.get(f"/api/meetings/{meeting['id']}", "participant").json()
        self.assertNotIn("analysis", detail)
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}", "secretary").json()["analysis"]["actions"][0]["status"], "in_progress")

    def test_review_rejects_unknown_assignee(self):
        meeting = self.ready_meeting()
        meeting["analysis"]["actions"][0]["assignee_id"] = "missing"
        self.assertEqual(self.review(meeting).status_code, 422)


class UserManagementTests(AppTestCase):
    def test_only_admin_manages_users(self):
        self.assertEqual(self.get("/api/users", "secretary").status_code, 403)
        payload = {"email": "new@example.kz", "name": "Новый", "role": "secretary", "password": "long-enough-password"}
        self.assertEqual(self.client.post("/api/users", headers=self.auth("secretary"), json=payload).status_code, 403)
        self.assertEqual(self.client.post("/api/users", headers=self.auth("admin"), json=payload).status_code, 201)
        self.assertEqual(self.client.post("/api/users", headers=self.auth("admin"), json=payload).status_code, 409)
        self.assertEqual(self.client.post("/api/users", headers=self.auth("admin"), json=payload | {"email": "short@example.kz", "password": "short"}).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "NEW@example.kz", "password": "long-enough-password"}).status_code, 200)

    def test_deactivation_revokes_sessions_and_protects_last_admin(self):
        target = self.users["chair"]["id"]
        self.assertEqual(self.client.patch(f"/api/users/{target}", headers=self.auth("admin"), json={"active": False}).status_code, 200)
        self.assertEqual(self.get("/api/auth/me", "chair").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "chair@example.kz", "password": PASSWORD}).status_code, 401)
        admin = self.users["admin"]["id"]
        self.assertEqual(self.client.patch(f"/api/users/{admin}", headers=self.auth("admin"), json={"role": "secretary"}).status_code, 409)

    def test_directory_is_limited(self):
        self.assertEqual(self.get("/api/users/directory", "chair").status_code, 200)
        self.assertNotIn("email", self.get("/api/users/directory", "secretary").json()[0])
        self.assertEqual(self.get("/api/users/directory", "participant").status_code, 403)


class AuditTests(AppTestCase):
    def test_audit_log_records_sensitive_actions(self):
        meeting = self.ready_meeting()
        self.get(f"/api/meetings/{meeting['id']}/audio", "secretary")
        self.get(f"/api/meetings/{meeting['id']}/export/docx", "secretary")
        self.client.post("/api/auth/login", json={"email": "secretary@example.kz", "password": "wrong"})
        self.assertEqual(self.get("/api/audit", "secretary").status_code, 403)
        entries = self.get("/api/audit", "auditor").json()
        actions = {entry["action"] for entry in entries}
        self.assertTrue({"login", "login_failed", "meeting_created", "audio_opened", "meeting_exported"} <= actions)
        scoped = self.get(f"/api/audit?meeting_id={meeting['id']}", "admin").json()
        self.assertTrue(all(entry["meeting_id"] == meeting["id"] for entry in scoped))
        self.assertNotIn(PASSWORD, str(entries))


if __name__ == "__main__":
    unittest.main()
