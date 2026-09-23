from datetime import datetime, timezone

from app.store import new_meeting
from tests.helpers import AppTestCase


class DashboardTests(AppTestCase):
    def test_empty_metrics_have_full_calendar_and_zero_actions(self):
        metrics = self.store.dashboard_metrics(datetime(2026, 9, 23, tzinfo=timezone.utc))
        self.assertEqual(len(metrics['daily_uploads']), 30)
        self.assertEqual(metrics['daily_uploads'][0], {'date': '2026-08-25', 'count': 0})
        self.assertEqual(metrics['daily_uploads'][-1], {'date': '2026-09-23', 'count': 0})
        self.assertEqual(metrics['actions']['total'], 0)

    def test_local_date_boundaries_and_only_reviewable_actions(self):
        for timestamp, status, actions in [
            ('2026-09-22T20:00:00+00:00', 'ready', [{'status': 'open', 'needs_review': True}, {'status': 'done'}]),
            ('2026-08-24T20:00:00+00:00', 'approved', [{'status': 'in_progress'}]),
            ('2026-08-24T18:00:00+00:00', 'failed', [{'status': 'done'}]),
            ('2026-09-24T00:00:00+00:00', 'queued', []),
        ]:
            meeting = new_meeting('Private title', '2026-09-23', 'private-audio')
            meeting.update(created_at=timestamp, status=status, analysis={'actions': actions})
            self.store.create(meeting)
        metrics = self.store.dashboard_metrics(datetime(2026, 9, 23, tzinfo=timezone.utc))
        self.assertEqual(sum(day['count'] for day in metrics['daily_uploads']), 2)
        self.assertEqual(metrics['daily_uploads'][-1]['count'], 1)
        self.assertEqual(metrics['daily_uploads'][0]['count'], 1)
        self.assertEqual(metrics['actions'], {'total': 3, 'open': 1, 'in_progress': 1, 'done': 1, 'needs_review': 1})
        self.assertNotIn('Private title', str(metrics))
        self.assertNotIn('private-audio', str(metrics))

    def test_overview_is_admin_only_and_returns_aggregates(self):
        meeting = self.ready_meeting()
        response = self.get('/api/admin/overview', 'admin')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['metrics']['actions']['total'], len(meeting['analysis']['actions']))
        self.assertNotIn('transcript', response.json()['metrics'])
        for role in ['secretary', 'participant', 'auditor']:
            self.assertEqual(self.get('/api/admin/overview', role).status_code, 403)
