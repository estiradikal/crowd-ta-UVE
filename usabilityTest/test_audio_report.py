import uuid

from django.test import TestCase
from django.urls import reverse

from .audio_report import build_audio_report
from .models import AudioMonitoringSession

class OwnAudioReportTests(TestCase):
    def setUp(self):
        self.record = AudioMonitoringSession.objects.create(
            session_id=uuid.uuid4(), subject_id='own-participant', task_id='1',
            finalized=True, duration_seconds=10, speech_seconds=10,
        )
        self.url = reverse('own_audio_report_pdf', args=[self.record.session_id])

    def login_participant(self, subject):
        session = self.client.session
        session['payid'] = subject
        session.save()

    def test_owner_without_admin_can_download(self):
        self.login_participant('own-participant')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_other_participant_cannot_download(self):
        self.login_participant('another-participant')
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_no_session_cannot_download(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_partial_record_is_not_downloaded_automatically(self):
        self.login_participant('own-participant')
        self.record.finalized = False
        self.record.save()
        self.assertEqual(self.client.get(self.url).status_code, 409)

    def test_download_requires_get(self):
        self.login_participant('own-participant')
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_audio_section_registered_in_admin(self):
        from django.contrib import admin
        self.assertIn(AudioMonitoringSession, admin.site._registry)

    def test_partial_zero_data_report(self):
        self.record.finalized = False
        self.record.duration_seconds = self.record.speech_seconds = 0
        self.record.events = []
        self.assertTrue(build_audio_report([self.record]).startswith(b'%PDF-'))

    def test_long_history_report(self):
        self.record.subject_id = '<participant>&'
        self.record.events = [{'type': 'silence_warning', 'at_seconds': i} for i in range(250)]
        self.assertTrue(build_audio_report([self.record]).startswith(b'%PDF-'))


class AdminAudioReportTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.admin_user = get_user_model().objects.create_superuser('audio-admin', 'test@example.org', 'test-password')
        self.record = AudioMonitoringSession.objects.create(
            session_id=uuid.uuid4(), subject_id='participant', task_id='1', finalized=True)
        self.url = reverse('admin:usabilityTest_audiomonitoringsession_pdf', args=[self.record.pk])

    def test_admin_downloads_pdf(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF-'))

    def test_staff_without_view_permission_is_denied(self):
        from django.contrib.auth import get_user_model
        staff = get_user_model().objects.create_user('audio-staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_unfinished_session_returns_conflict(self):
        self.client.force_login(self.admin_user)
        self.record.finalized = False
        self.record.save()
        self.assertEqual(self.client.get(self.url).status_code, 409)

    def test_record_cannot_be_edited_in_admin(self):
        self.client.force_login(self.admin_user)
        url = reverse('admin:usabilityTest_audiomonitoringsession_change', args=[self.record.pk])
        self.assertEqual(self.client.post(url, {'subject_id': 'changed'}).status_code, 403)
        self.record.refresh_from_db()
        self.assertEqual(self.record.subject_id, 'participant')
