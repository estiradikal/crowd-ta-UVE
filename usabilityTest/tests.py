import json
import os
import shutil

from django.contrib.auth.models import User
from django.test import TestCase

from .evaluation_views import resumen_problemas
from .models import Anotacion, CatalogoProblema, Evaluacion, ProblemaIdentificado

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
TEST_UPLOAD_DIR = os.path.join(UPLOADS_DIR, 'testpay')


class EvaluarVideoPageTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='evaluador-test', password='x')
        user.is_staff = True
        user.save()
        self.client.force_login(user)

        self.evaluacion = Evaluacion.objects.create(
            video_id='test.webm',
            payment_id='testpay',
            task_id='testtask',
        )

        task_dir = os.path.join(TEST_UPLOAD_DIR, 'testtask', '2026-01-01')
        os.makedirs(task_dir, exist_ok=True)
        with open(os.path.join(task_dir, 'test.webm'), 'wb') as fh:
            fh.write(b'fake-video')

    def tearDown(self):
        shutil.rmtree(TEST_UPLOAD_DIR, ignore_errors=True)

    def test_page_renders_problem_combobox_and_modal(self):
        resp = self.client.get('/admin-panel/evaluar/testpay/testtask/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('id="formProblemText"', body)
        self.assertIn('id="formProblemId"', body)
        self.assertIn('id="problemListbox"', body)
        self.assertIn('Select an existing problem or create a new one.', body)
        self.assertIn('id="registerProblemModal"', body)
        self.assertIn('Create new problem', body)
        self.assertIn('<th>Problem</th>', body)
        # problem creation lives only in the New Annotation combobox now
        self.assertIn('id="problemSelect"', body)
        self.assertNotIn('id="newProblemModal"', body)
        self.assertNotIn('id="btnSaveNewProblem"', body)
        self.assertNotIn('+ New Problem', body)
        # filtering is prefix-based: every visible item starts with what was typed
        self.assertIn('indexOf(q) === 0', body)

    def test_annotation_saves_problema_field(self):
        payload = {
            'start_time': '00:10',
            'finish_time': '00:20',
            'problema': 'Navigation unclear',
            'indicador': 'ACT',
            'contexto': 'Main task',
            'comentarios': 'comment',
        }
        resp = self.client.post(
            '/admin-panel/api/%d/anotacion/' % self.evaluacion.id,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('ok'))
        ann = Anotacion.objects.get(evaluacion=self.evaluacion)
        self.assertEqual(ann.problema, 'Navigation unclear')

    def test_create_catalog_problem_endpoint(self):
        resp = self.client.post(
            '/admin-panel/api/catalogo-problemas/crear/',
            data=json.dumps({'descripcion': 'Colores poco contrastantes'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))
        self.assertTrue(data['codigo'].startswith('PROB-'))
        self.assertEqual(data['descripcion'], 'Colores poco contrastantes')


class AnnotationSheetTests(TestCase):
    """Pestanas tipo Excel: edicion de anotaciones/problemas y resumen de ocurrencias."""

    def setUp(self):
        user = User.objects.create_user(username='evaluador-sheet', password='x', is_staff=True)
        self.client.force_login(user)
        self.evaluacion = Evaluacion.objects.create(video_id='_mw-abc_.webm', payment_id='pay1', task_id='1')
        self.p1 = CatalogoProblema.objects.create(descripcion='Images take several seconds to load')
        self.p2 = CatalogoProblema.objects.create(descripcion='Instructions too long')

    def post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def add_annotation(self, problema, start='00:10', finish='00:14'):
        resp = self.post('/admin-panel/api/%d/anotacion/' % self.evaluacion.id, {
            'start_time': start, 'finish_time': finish, 'problema_id': problema.id,
            'indicador': 'DSF', 'contexto': 'Main task', 'comentarios': '',
        })
        self.assertEqual(resp.status_code, 200)
        return Anotacion.objects.get(id=resp.json()['id'])

    def test_annotation_links_to_catalog(self):
        ann = self.add_annotation(self.p1)
        self.assertEqual(ann.problema_ref, self.p1)
        self.assertEqual(ann.problema, self.p1.descripcion)

    def test_edit_annotation(self):
        ann = self.add_annotation(self.p1)
        resp = self.post('/admin-panel/api/anotacion/%d/editar/' % ann.id, {
            'start_time': '01:02', 'finish_time': '', 'problema_id': self.p2.id,
            'indicador': 'PUZZ', 'contexto': 'Training', 'comentarios': 'fixed',
        })
        self.assertEqual(resp.status_code, 200)
        ann.refresh_from_db()
        self.assertEqual((ann.start_time, ann.finish_time, ann.indicador, ann.contexto, ann.comentarios),
                         ('01:02', '', 'PUZZ', 'Training', 'fixed'))
        self.assertEqual(ann.problema_ref, self.p2)
        self.assertEqual(ann.problema, self.p2.descripcion)

    def test_edit_annotation_rejects_bad_times(self):
        ann = self.add_annotation(self.p1)
        url = '/admin-panel/api/anotacion/%d/editar/' % ann.id
        self.assertEqual(self.post(url, {'start_time': '1:2:3'}).status_code, 400)
        self.assertEqual(self.post(url, {'start_time': '00:20', 'finish_time': '00:10'}).status_code, 400)

    def test_edit_problem_changes_classification_and_text(self):
        ann = self.add_annotation(self.p1)
        pi = ProblemaIdentificado.objects.create(evaluacion=self.evaluacion, problema=self.p1,
                                                 severidad='Serious', tipo='Content')
        resp = self.post('/admin-panel/api/problema/%d/editar/' % pi.id, {
            'problema_id': self.p1.id, 'descripcion': 'Images load slowly',
            'severidad': 'Critical', 'tipo': 'Functionality', 'comentarios': 'c',
        })
        self.assertEqual(resp.status_code, 200)
        pi.refresh_from_db()
        ann.refresh_from_db()
        self.assertEqual((pi.severidad, pi.tipo), ('Critical', 'Functionality'))
        self.assertEqual(pi.problema.descripcion, 'Images load slowly')
        self.assertEqual(ann.problema, 'Images load slowly')

    def test_edit_problem_swap_moves_annotations(self):
        ann = self.add_annotation(self.p1)
        pi = ProblemaIdentificado.objects.create(evaluacion=self.evaluacion, problema=self.p1,
                                                 severidad='Serious', tipo='Content')
        self.post('/admin-panel/api/problema/%d/editar/' % pi.id, {'problema_id': self.p2.id})
        ann.refresh_from_db()
        self.assertEqual(ann.problema_ref, self.p2)

    def test_resumen_counts_and_average(self):
        self.add_annotation(self.p1, '00:10', '00:14')
        self.add_annotation(self.p1, '00:20', '00:22')
        self.add_annotation(self.p1, '00:30', '')
        self.add_annotation(self.p2, '00:40', '00:50')
        filas, totales = resumen_problemas(self.evaluacion.anotaciones.select_related('problema_ref'))
        self.assertEqual(totales, {'anotaciones': 4, 'problemas_distintos': 2, 'promedio_por_problema': 2.0})
        self.assertEqual(filas[0]['descripcion'], self.p1.descripcion)
        self.assertEqual(filas[0]['ocurrencias'], 3)
        self.assertEqual(filas[0]['porcentaje'], 75.0)
        self.assertEqual(filas[0]['duracion_promedio'], 3.0)

    def test_tabla_anotaciones_page(self):
        self.add_annotation(self.p1)
        resp = self.client.get('/admin-panel/tabla-anotaciones/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        for col in ('video_id', 'start_time', 'finish_time', 'indicator_code', 'task_moment', 'problem', 'comments'):
            self.assertIn('<th>%s</th>' % col, body)
        self.assertIn('_mw-abc_', body)
        self.assertIn('Average occurrences per problem', body)


class TimeAnnotationAndGuideTests(TestCase):
    """Hoja '3. Time annotation' y panel lateral de la guia."""

    def setUp(self):
        self.user = User.objects.create_user(username='evaluador-time', password='x', is_staff=True)
        self.client.force_login(self.user)
        task_dir = os.path.join(UPLOADS_DIR, 'timepay', '1', '2026-01-01')
        os.makedirs(task_dir, exist_ok=True)
        with open(os.path.join(task_dir, '_mw-time_.webm'), 'wb') as fh:
            fh.write(b'fake-video')

    def tearDown(self):
        shutil.rmtree(os.path.join(UPLOADS_DIR, 'timepay'), ignore_errors=True)

    def open_page(self):
        resp = self.client.get('/admin-panel/evaluar/timepay/1/')
        self.assertEqual(resp.status_code, 200)
        return resp, Evaluacion.objects.get(payment_id='timepay', task_id='1')

    def test_opening_sets_start_time_and_evaluator_once(self):
        _, ev = self.open_page()
        self.assertIsNotNone(ev.fecha_inicio)
        self.assertEqual(ev.evaluador, 'evaluador-time')
        inicio = ev.fecha_inicio
        _, ev = self.open_page()
        self.assertEqual(ev.fecha_inicio, inicio)

    def test_active_time_accumulates_and_is_capped(self):
        _, ev = self.open_page()
        url = '/admin-panel/api/%d/tiempo/' % ev.id
        self.assertEqual(self.client.post(url, {'segundos': 30}).json()['tiempo_activo_segundos'], 30)
        self.assertEqual(self.client.post(url, {'segundos': 99999}).json()['tiempo_activo_segundos'], 150)
        self.assertEqual(self.client.post(url, {'segundos': -50}).json()['tiempo_activo_segundos'], 150)
        self.assertEqual(self.client.post(url, {'segundos': 'abc'}).status_code, 400)

    def test_finish_sets_duration(self):
        _, ev = self.open_page()
        self.client.post('/admin-panel/api/%d/completar/' % ev.id, data='{}', content_type='application/json')
        ev.refresh_from_db()
        self.assertIsNotNone(ev.fecha_fin)
        self.assertIsNotNone(ev.duracion_segundos)
        self.assertRegex(ev.duracion_texto, r'^\d{2}:\d{2}:\d{2}$')

    def test_time_sheet_tab_and_guide_panel_render(self):
        resp, _ = self.open_page()
        body = resp.content.decode()
        self.assertIn('3. Time annotation', body)
        for col in ('annotation_start_time', 'annotation_finish_time', 'duration'):
            self.assertIn('<th>%s</th>' % col, body)
        self.assertIn('id="guideDrawer"', body)
        self.assertIn('id="btnOpenGuide"', body)
        self.assertIn('data-open-guide="indicators"', body)
        tabla = self.client.get('/admin-panel/tabla-anotaciones/').content.decode()
        self.assertIn('3. Time annotation', tabla)
        self.assertIn('_mw-time_', tabla)
