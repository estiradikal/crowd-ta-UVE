import json
import uuid

from django.test import TestCase
from django.urls import reverse

from .models import AudioMonitoringSession, SubjectProfile, TasksDescription

class AudioMonitoringEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse('audio_monitoring')
        self.session_id = str(uuid.uuid4())
        session = self.client.session
        session['payid'] = 'subject-test'
        session.save()

    def payload(self, final=False):
        return {
            'session_id': self.session_id,
            'task_id': '1',
            'client_version': 'test',
            'final': final,
            'metrics': {
                'durationSeconds': 35,
                'speechSeconds': 20,
                'silenceSeconds': 10,
                'noiseSeconds': 5,
                'averageSpeechProbability': 0.61,
                'musicAlerts': 1,
            },
            'events': [{
                'type': 'audio_warning',
                'label': 'MÚSICA PROBABLE',
                'at_seconds': 18.4,
                'confidence': 0.73,
                'details': {},
            }],
        }

    def test_creates_and_finalizes_monitoring_session(self):
        response = self.client.post(
            self.url,
            data=json.dumps(self.payload(final=True)),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        record = AudioMonitoringSession.objects.get(session_id=self.session_id)
        self.assertTrue(record.finalized)
        self.assertEqual(record.subject_id, 'subject-test')
        self.assertEqual(record.music_alerts, 1)
        self.assertEqual(len(record.events), 1)

    def test_rejects_request_without_crowdta_session(self):
        self.client.session.flush()
        response = self.client.post(
            self.url,
            data=json.dumps(self.payload()),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_rejects_invalid_payload(self):
        response = self.client.post(self.url, data='{', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_task_page_loads_production_audio_modules(self):
        SubjectProfile.objects.create(
            age=25,
            gender='other',
            birth_country='CO',
            residence_country='CO',
            mother_tongue='Spanish',
            Do_you_speak_English='yes',
            participated_before='no',
            knowledge_on_usability='basic',
            payment_id='subject-test',
            workerId='1',
            campId='1',
            groupId='1',
        )
        TasksDescription.objects.create(
            task_id='1',
            task_description='Test task',
            task_valid_question='Question',
            valid_ans_options='one|two',
            answer='one',
        )
        response = self.client.get(reverse('test_page', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'audio-monitoring-session.js')
        self.assertContains(response, 'music-monitor.js')
        self.assertContains(response, 'vad-monitor.js')
        self.assertContains(response, 'audio-sync-status')

    def test_saves_participant_timezone(self):
        payload = self.payload(final=True)
        payload['client_timezone'] = 'Europe/Madrid'
        payload['client_utc_offset_minutes'] = -120
        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        record = AudioMonitoringSession.objects.get(session_id=self.session_id)
        self.assertEqual(record.client_timezone, 'Europe/Madrid')
        self.assertEqual(record.client_utc_offset_minutes, -120)
