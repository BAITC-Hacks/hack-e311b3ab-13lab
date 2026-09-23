"""End-to-end run on PostgreSQL and MinIO. Skipped unless these are set:

    HATTAMA_TEST_DATABASE_URL=postgresql://hattama:secret@127.0.0.1:55432/hattama
    HATTAMA_TEST_MINIO_ENDPOINT=127.0.0.1:59000
    HATTAMA_TEST_MINIO_ACCESS_KEY=... HATTAMA_TEST_MINIO_SECRET_KEY=...

The test drops and recreates all tables in that database.
"""

import os
import unittest
import uuid

from sqlalchemy import create_engine

from app.store import database_url, metadata
from tests.helpers import AppTestCase, make_settings

DATABASE = os.getenv("HATTAMA_TEST_DATABASE_URL", "")
MINIO = os.getenv("HATTAMA_TEST_MINIO_ENDPOINT", "")


@unittest.skipUnless(DATABASE and MINIO, "set HATTAMA_TEST_DATABASE_URL and HATTAMA_TEST_MINIO_ENDPOINT")
class PostgresMinioTests(AppTestCase):
    def setUp(self):
        bucket = f"hattama-test-{uuid.uuid4().hex[:8]}"
        self.settings_overrides = {
            "database_url": DATABASE,
            "minio_endpoint": MINIO,
            "minio_access_key": os.getenv("HATTAMA_TEST_MINIO_ACCESS_KEY", ""),
            "minio_secret_key": os.getenv("HATTAMA_TEST_MINIO_SECRET_KEY", ""),
            "minio_bucket": bucket,
        }
        engine = create_engine(database_url(make_settings(".", database_url=DATABASE)))
        metadata.drop_all(engine)
        engine.dispose()
        super().setUp()

    def tearDown(self):
        blobs = self.app.state.blobs
        for item in blobs.client.list_objects(blobs.bucket, recursive=True):
            blobs.client.remove_object(blobs.bucket, item.object_name)
        blobs.client.remove_bucket(blobs.bucket)
        super().tearDown()

    def test_full_workflow(self):
        self.assertEqual(self.store.backend, "postgresql")
        self.assertEqual(self.app.state.blobs.kind, "minio")
        meeting = self.ready_meeting()
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/audio", "secretary").content, b"audio")
        meeting["analysis"]["actions"][0]["assignee_id"] = self.users["participant"]["id"]
        saved = self.review(meeting)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(self.review(meeting).status_code, 409)
        approved = self.approve(saved.json())
        for fmt in approved["approvals"][0]["formats"]:
            self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/approved/{fmt}", "secretary").status_code, 200)
        action_id = approved["analysis"]["actions"][0]["id"]
        response = self.client.patch(f"/api/meetings/{meeting['id']}/actions/{action_id}", headers=self.auth("participant"), json={"status": "done"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("meeting_approved", {entry["action"] for entry in self.get("/api/audit", "auditor").json()})
        self.assertEqual(self.client.delete(f"/api/meetings/{meeting['id']}", headers=self.auth("secretary")).status_code, 204)
        self.assertEqual(list(self.app.state.blobs.client.list_objects(self.app.state.blobs.bucket, recursive=True)), [])


if __name__ == "__main__":
    unittest.main()
