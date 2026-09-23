import unittest
from io import BytesIO

from docx import Document

from app import exports
from tests.helpers import AppTestCase

HAS_PDF_FONT = exports.find_fonts(type("S", (), {"pdf_font_path": "", "pdf_font_bold_path": ""})()) is not None


class ProtocolFileTests(AppTestCase):
    def test_approval_archives_docx_and_pdf(self):
        meeting = self.approve(self.ready_meeting())
        self.assertEqual(meeting["approvals"][0]["formats"], ["docx", "pdf"] if HAS_PDF_FONT else ["docx"])
        self.assertNotIn("files", meeting["approvals"][0])
        archived = self.get(f"/api/meetings/{meeting['id']}/approved/docx", "secretary")
        self.assertEqual(archived.status_code, 200)
        self.assertIn("Протокол утверждён", "\n".join(paragraph.text for paragraph in Document(BytesIO(archived.content)).paragraphs))
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/approved/xml", "secretary").status_code, 404)
        self.assertTrue((self.settings.data_dir / "protocols" / meeting["id"]).is_dir())
        self.assertEqual(self.client.delete(f"/api/meetings/{meeting['id']}", headers=self.auth("secretary")).status_code, 204)
        self.assertFalse((self.settings.data_dir / "protocols" / meeting["id"]).exists())

    @unittest.skipUnless(HAS_PDF_FONT, "no Cyrillic TTF font found on this machine")
    def test_pdf_export(self):
        meeting = self.ready_meeting()
        response = self.get(f"/api/meetings/{meeting['id']}/export/pdf", "secretary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        archived = self.get(f"/api/meetings/{self.approve(meeting)['id']}/approved/pdf", "secretary")
        self.assertTrue(archived.content.startswith(b"%PDF-"))


class MissingFontTests(AppTestCase):
    settings_overrides = {"pdf_font_path": "/nonexistent/font.ttf"}

    def test_pdf_unavailable_without_font(self):
        meeting = self.ready_meeting()
        self.assertEqual(self.get(f"/api/meetings/{meeting['id']}/export/pdf", "secretary").status_code, 503)
        approved = self.approve(meeting)
        self.assertEqual(approved["approvals"][0]["formats"], ["docx"])
        self.assertTrue(approved["warnings"])
        self.assertFalse(self.client.get("/api/health").json()["pdf_configured"])


if __name__ == "__main__":
    unittest.main()
