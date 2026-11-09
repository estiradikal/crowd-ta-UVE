import json
import os
import shutil
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from .evaluation_views import resumen_problemas
from .models import Anotacion, CatalogoProblema, Evaluacion, ProblemaIdentificado, SubjectProfile, Test_Input

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
        self.assertNotIn('id="problemSelect"', body)
        self.assertNotIn('id="problemForm"', body)
        self.assertNotIn('id="newProblemModal"', body)
        self.assertNotIn('id="btnSaveNewProblem"', body)
        self.assertNotIn('+ New Problem', body)
        # filtering is prefix-based: every visible item starts with what was typed
        self.assertIn('indexOf(q) === 0', body)

    def test_page_renders_resizable_layout(self):
        resp = self.client.get('/admin-panel/evaluar/testpay/testtask/')
        body = resp.content.decode()
        self.assertIn('id="evalSplit"', body)
        self.assertIn('id="gutterVideo"', body)
        self.assertIn('id="gutterSide"', body)
        self.assertIn('id="sidebarResizer"', body)
        # New Annotation lives in the right-hand panel
        side = body.index('id="paneSide"')
        self.assertGreater(body.index('id="annotationForm"'), side)
        # Times are marked with the S / E shortcuts (documented in the guide); no Mark buttons
        self.assertNotIn('Time Controls', body)
        self.assertNotIn('id="btnMarkStart"', body)
        self.assertNotIn('id="btnMarkEnd"', body)
        self.assertIn('data-guide-section="shortcuts"', body)
        self.assertIn('data-open-guide="shortcuts"', body)
        # Annotations list sits right below the video, before Identified Problems
        self.assertLess(body.index('id="videoPlayer"'), body.index('id="annotationsList"'))
        self.assertLess(body.index('id="annotationsList"'), body.index('id="problemsList"'))
        self.assertIn('id="btnTheater"', body)

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

    def test_annotation_registers_existing_problem_once(self):
        # The same problem was already rated in another video: severity and type are reused
        otra = Evaluacion.objects.create(video_id='other.webm', payment_id='pay2', task_id='1')
        ProblemaIdentificado.objects.create(evaluacion=otra, problema=self.p1,
                                            severidad='Critical', tipo='Layout', comentarios='other video')
        resp = self.post('/admin-panel/api/%d/anotacion/' % self.evaluacion.id, {
            'start_time': '00:10', 'finish_time': '00:14', 'problema_id': self.p1.id,
            'indicador': 'DSF', 'contexto': 'Main task', 'comentarios': '',
        })
        nuevo = resp.json()['problema']
        self.assertEqual(nuevo['problema_id'], self.p1.id)
        self.assertEqual((nuevo['severidad'], nuevo['tipo'], nuevo['comentarios']), ('Critical', 'Layout', ''))

        # A second annotation of the same problem does not duplicate it
        resp = self.post('/admin-panel/api/%d/anotacion/' % self.evaluacion.id, {
            'start_time': '00:30', 'finish_time': '', 'problema_id': self.p1.id,
            'indicador': 'REP', 'contexto': 'Main task', 'comentarios': '',
        })
        self.assertIsNone(resp.json()['problema'])
        self.assertEqual(self.evaluacion.problemas.filter(problema=self.p1).count(), 1)

    def test_problem_never_rated_is_registered_without_severity(self):
        self.add_annotation(self.p2)
        reg = self.evaluacion.problemas.get(problema=self.p2)
        self.assertEqual((reg.severidad, reg.tipo), ('', ''))

    def test_editing_annotation_to_other_problem_registers_it(self):
        ann = self.add_annotation(self.p1)
        resp = self.post('/admin-panel/api/anotacion/%d/editar/' % ann.id, {
            'start_time': '00:10', 'finish_time': '00:14', 'problema_id': self.p2.id,
            'indicador': 'DSF', 'contexto': 'Main task', 'comentarios': '',
        })
        self.assertEqual(resp.json()['problema']['problema_id'], self.p2.id)
        self.assertEqual(set(self.evaluacion.problemas.values_list('problema_id', flat=True)),
                         {self.p1.id, self.p2.id})

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
        self.assertIn('/admin-panel/tabla-anotaciones/excel/', body)

    def test_tabla_anotaciones_excel_has_one_sheet_per_tab(self):
        from io import BytesIO
        from django.utils import timezone
        from openpyxl import load_workbook
        self.add_annotation(self.p1, '00:10', '00:14')
        self.evaluacion.fecha_inicio = self.evaluacion.fecha_inicio or timezone.now()
        self.evaluacion.save()
        otra = Evaluacion.objects.create(video_id='_mw-otro_.webm', payment_id='pay2', task_id='2')
        Anotacion.objects.create(evaluacion=otra, start_time='00:01', indicador='ACT', contexto='Training',
                                 problema='Otro problema')

        resp = self.client.get('/admin-panel/tabla-anotaciones/excel/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])
        self.assertIn('attachment;', resp['Content-Disposition'])
        wb = load_workbook(BytesIO(resp.content))
        self.assertEqual(wb.sheetnames,
                         ['1. Annotation table', '2. Problem table', '3. Time annotation', 'Problem summary'])
        anot = wb['1. Annotation table']
        self.assertEqual([c.value for c in anot[1]],
                         ['video_id', 'start_time', 'finish_time', 'indicator_code', 'task_moment', 'problem', 'comments'])
        self.assertEqual(anot.max_row, 3)  # encabezado + 2 anotaciones
        self.assertEqual([c.value for c in anot[2]][:5], ['_mw-abc_', '00:10', '00:14', 'DSF', 'Main task'])
        self.assertEqual(wb['2. Problem table']['B2'].value, self.p1.codigo)
        self.assertEqual(wb['3. Time annotation']['A2'].value, '_mw-abc_')
        self.assertTrue(wb['Problem summary']['A1'].value.startswith('Video: _mw-abc_'))

        # Con el filtro de video solo sale ese video
        resp = self.client.get('/admin-panel/tabla-anotaciones/excel/?video=%d' % otra.id)
        anot = load_workbook(BytesIO(resp.content))['1. Annotation table']
        self.assertEqual(anot.max_row, 2)
        self.assertEqual(anot['A2'].value, '_mw-otro_')


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


class DashboardTests(TestCase):
    """El dashboard calcula el progreso por estado, campaña, tarea, severidad e indicador."""

    def setUp(self):
        self.user = User.objects.create_user(username='dash-eval', password='x', is_staff=True, first_name='Ana')
        self.client.force_login(self.user)
        # Solo los videos de la prueba, no los de la carpeta uploads real
        videos = [{'payment_id': 'testpay', 'worker_id': 'W-77', 'task_id': t, 'date': '2026-01-01',
                   'filename': 'v.webm'} for t in ('t1', 't2')]
        patcher = mock.patch('usabilityTest.evaluation_views.get_uploaded_videos', side_effect=lambda: list(videos))
        self.videos = videos
        patcher.start()
        self.addCleanup(patcher.stop)
        SubjectProfile.objects.create(payment_id='testpay', age=30, gender='F', participated_before='no',
                                      knowledge_on_usability='no', workerId='W-77', campId='camp-a')
        done = Evaluacion.objects.create(video_id='v.webm', payment_id='testpay', task_id='t1', completada=True,
                                         evaluador='dash-eval', tiempo_activo_segundos=120)
        problema = CatalogoProblema.objects.create(descripcion='No encuentra el menú')
        ProblemaIdentificado.objects.create(evaluacion=done, problema=problema, severidad='Critical', tipo='Navigation')
        Anotacion.objects.create(evaluacion=done, start_time='00:01', indicador='PUZZ', contexto='Main task')

    def test_dashboard_shows_charts_with_real_counts(self):
        response = self.client.get('/admin-panel/')
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx['progress_legend'][0]['value'], 1)       # completados
        self.assertEqual(ctx['progress_legend'][2]['value'], 1)       # pendientes
        self.assertEqual(ctx['progress_pct'], 50)
        self.assertEqual([r['key'] for r in ctx['campaign_rows']], ['camp-a'])
        self.assertEqual(sorted(r['key'] for r in ctx['task_rows']), ['t1', 't2'])
        self.assertEqual(ctx['severity_legend'][0]['value'], 1)
        self.assertEqual(ctx['top_indicators'][0]['code'], 'PUZZ')
        self.assertEqual(ctx['avg_time'], '2m 00s')
        self.assertContains(response, 'Campaign camp-a')
        self.assertNotContains(response, 'Evaluate next video')
        self.assertNotContains(response, 'Top evaluators')
        self.assertNotContains(response, 'Quick Actions')

    def test_dashboard_without_data(self):
        self.videos.clear()
        Evaluacion.objects.all().delete()
        response = self.client.get('/admin-panel/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No videos available')


class CampaignsPageTests(TestCase):
    """Las campañas se registran desde el enlace del participante y muestran su estado como los videos."""

    def setUp(self):
        self.user = User.objects.create_user(username='camp-eval', password='x', is_staff=True)
        self.client.force_login(self.user)
        videos = [{'payment_id': pay, 'worker_id': pay, 'task_id': '1', 'date': '2026-01-01', 'filename': '_v.webm'}
                  for pay in ('pay-a1', 'pay-a2', 'pay-b1', 'pay-sin-perfil')]
        patcher = mock.patch('usabilityTest.evaluation_views.get_uploaded_videos', side_effect=lambda: list(videos))
        patcher.start()
        self.addCleanup(patcher.stop)
        for pay, camp in (('pay-a1', 'camp-a'), ('pay-a2', 'camp-a'), ('pay-b1', 'camp-b')):
            SubjectProfile.objects.create(payment_id=pay, age=30, gender='F', participated_before='no',
                                          knowledge_on_usability='no', workerId=pay, campId=camp)
            Test_Input.objects.get_or_create(campId=camp)
        Test_Input.objects.create(campId='camp-c')
        # Participante del enlace por defecto: no pertenece a ninguna campaña
        SubjectProfile.objects.create(payment_id='pay-demo', age=30, gender='F', participated_before='no',
                                      knowledge_on_usability='no', workerId='DEMO2', campId='demo')
        Test_Input.objects.create(campId='demo')
        Evaluacion.objects.create(video_id='v.webm', payment_id='pay-a1', task_id='1', completada=True)
        Evaluacion.objects.create(video_id='v.webm', payment_id='pay-a2', task_id='1', completada=True)
        Evaluacion.objects.create(video_id='v.webm', payment_id='pay-b1', task_id='1', completada=False)

    def test_table_like_videos_without_evaluate(self):
        response = self.client.get('/admin-panel/campanas/')
        filas = [(f['camp_id'], f['worker_id']) for f in response.context['videos']]
        # Los videos sin campaña (pay-sin-perfil) y los del enlace por defecto (DEMO2) no aparecen
        self.assertEqual(filas, [('camp-a', 'pay-a1'), ('camp-a', 'pay-a2'), ('camp-b', 'pay-b1')])
        self.assertNotContains(response, 'pay-sin-perfil')
        self.assertNotContains(response, 'DEMO2')
        self.assertNotContains(response, '/admin-panel/evaluar/')
        self.assertContains(response, 'data-copy="camp-a"')
        self.assertContains(response, 'data-copy="pay-a1"')
        self.assertContains(response, 'data-copy="v"')  # nombre del archivo, como en la lista de Videos
        self.assertContains(response, 'status-completada')
        self.assertContains(response, 'status-progreso')

    def test_filters_and_search(self):
        response = self.client.get('/admin-panel/campanas/?filtro=en_progreso')
        self.assertEqual([f['worker_id'] for f in response.context['videos']], ['pay-b1'])
        response = self.client.get('/admin-panel/campanas/?filtro=completadas')
        self.assertEqual([f['worker_id'] for f in response.context['videos']], ['pay-a1', 'pay-a2'])
        response = self.client.get('/admin-panel/campanas/?q=CAMP-B')
        self.assertEqual([f['worker_id'] for f in response.context['videos']], ['pay-b1'])
        response = self.client.get('/admin-panel/campanas/?q=pay-a2')
        self.assertEqual([f['worker_id'] for f in response.context['videos']], ['pay-a2'])

    def test_view_videos_of_a_campaign(self):
        response = self.client.get('/admin-panel/videos/?camp=camp-a')
        self.assertEqual(sorted(v['payment_id'] for v in response.context['videos']), ['pay-a1', 'pay-a2'])

    def test_participant_link_registers_the_campaign(self):
        self.client.get('/index/?groupId=1&campId=nueva-campana&workerId=w1')
        self.assertTrue(Test_Input.objects.filter(campId='nueva-campana').exists())

