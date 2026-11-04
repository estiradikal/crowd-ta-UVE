from pathlib import Path

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from .models import InstructionsPage, SubjectProfile, TasksDescription


class DevelopIntegrationTests(TestCase):
    def setUp(self):
        self.profile = SubjectProfile.objects.create(
            payment_id='merge-participant', age=25, gender='M',
            birth_country='CO', residence_country='CO',
            participated_before='False', knowledge_on_usability='False',
            workerId='worker-merge', campId='campaign-merge', groupId='1')
        self.task = TasksDescription.objects.create(task_id='1', task_description='Task text',
            task_valid_question='Question', answer='answer')
        InstructionsPage.objects.create(key='general_instructions', content_md='# Instructions from database')
        session = self.client.session
        session['payid'] = self.profile.pk
        session['workerId'] = self.profile.workerId
        session['campId'] = self.profile.campId
        session.save()

    def test_markdown_and_instruction_admin_preserved(self):
        self.assertIn('Task text', self.task.markdown)
        self.assertIn('integration_enabled', self.task.markdown)
        self.assertIn(InstructionsPage, admin.site._registry)

    def test_default_task_keeps_develop_iframe_and_markdown(self):
        response = self.client.get(reverse('test_page', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['instructions_md'], '# Instructions from database')
        self.assertContains(response, 'id="iframe"')
        self.assertContains(response, 'mwId=worker-merge&amp;campId=campaign-merge')
        self.assertContains(response, 'marked.parse(source)')
        self.assertNotContains(response, 'id="task-application"')
        self.assertNotContains(response, 'www.edx.org')

    def test_integration_task_loads_gate_and_keeps_markdown(self):
        self.task.integration_enabled = True
        self.task.application_url = 'https://application.example/task'
        self.task.minimum_active_seconds = 15
        self.task.save()
        response = self.client.get(reverse('test_page', args=[1]))
        self.assertContains(response, 'id="task-application"')
        self.assertContains(response, 'data-url="https://application.example/task"')
        self.assertContains(response, 'data-minimum="15"')
        self.assertContains(response, 'task-integration.js')
        self.assertContains(response, 'audio-monitoring-session.js')
        self.assertContains(response, 'marked.parse(source)')
        self.assertContains(response, 'id="vad-warning-toast"')
        self.assertContains(response, 'id="music-warning-toast"')

    def test_develop_recording_restriction_preserved(self):
        js = (Path(__file__).parent / 'static/js/mediarecoder.js').read_text()
        self.assertIn("settings.displaySurface !== 'browser'", js)
        self.assertIn("monitorTypeSurfaces: 'exclude'", js)
        self.assertIn('await stopRecording()', js)
