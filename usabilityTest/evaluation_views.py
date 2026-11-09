import os
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required as _staff_member_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db import IntegrityError
from django.db.models import F, Q
from django.utils import timezone, translation

from .models import (Evaluacion, Anotacion, ProblemaIdentificado, CatalogoProblema, SubjectProfile, Test_Input, DEMO_CAMP_ID,
                     EvaluatorProfile, TasksDescription, parse_mmss)
from .forms import AccountForm, PreferencesForm, ShortcutsForm, Test_InputForm
from .panel_preferences import (ACCENT_COLORS, LANGUAGES, NAMED_KEYS, SHORTCUT_ACTIONS, accent_palette, accent_style,
                                resolve_shortcuts, shortcut_label, translate)


def staff_member_required(view_func):
    # Sin sesión, el panel manda al login propio en vez de al de /admin/
    return _staff_member_required(view_func, login_url='panel_login')


# Estados de un video en el dashboard: (clave, etiqueta, icono)
VIDEO_STATES = (
    ('completed', 'Completed', 'fa-check-circle'),
    ('in_progress', 'In Progress', 'fa-hourglass-half'),
    ('pending', 'Pending', 'fa-clock'),
)
SEVERITIES = (
    ('Critical', 'fa-exclamation-circle'),
    ('Serious', 'fa-exclamation-triangle'),
    ('Cosmetic', 'fa-paint-brush'),
)
MAX_BAR_ROWS = 6


def _donut(counts, keys):
    """Segmentos de un anillo SVG (círculo de perímetro 100) con un pequeño hueco entre ellos."""
    total = sum(counts.get(k, 0) for k in keys)
    segments, offset = [], 0.0
    shown = [k for k in keys if counts.get(k)]
    gap = 1.2 if len(shown) > 1 else 0
    for key in keys:
        value = counts.get(key, 0)
        pct = 100.0 * value / total if total else 0
        if value:
            segments.append({'key': key, 'value': value, 'pct': round(pct),
                             'dash': '%.2f %.2f' % (max(pct - gap, 0.5), 100 - max(pct - gap, 0.5)),
                             'offset': '%.2f' % (25 - offset)})
        offset += pct
    return total, segments


def _stacked_rows(groups, label_of):
    """Filas de barras apiladas completadas/en progreso/pendientes, la más grande primero."""
    rows = sorted(groups.items(), key=lambda kv: (-sum(kv[1].values()), str(kv[0])))
    if len(rows) > MAX_BAR_ROWS:
        other = {k: 0 for k, _, _ in VIDEO_STATES}
        for _, counts in rows[MAX_BAR_ROWS - 1:]:
            for k in other:
                other[k] += counts.get(k, 0)
        rows = rows[:MAX_BAR_ROWS - 1] + [(None, other)]
    biggest = max((sum(c.values()) for _, c in rows), default=0) or 1
    result = []
    for key, counts in rows:
        total = sum(counts.values())
        result.append({
            'key': key,
            'label': label_of(key),
            'total': total,
            'completed': counts.get('completed', 0),
            'pct_done': round(100.0 * counts.get('completed', 0) / total) if total else 0,
            'width': round(100.0 * total / biggest, 1),
            'segments': [{'key': k, 'value': counts.get(k, 0),
                          'pct': round(100.0 * counts.get(k, 0) / total, 2) if total else 0}
                         for k, _, _ in VIDEO_STATES if counts.get(k)],
        })
    return result


def _format_duration(seconds):
    seconds = int(seconds or 0)
    if seconds >= 3600:
        return '%dh %02dm' % (seconds // 3600, seconds % 3600 // 60)
    return '%dm %02ds' % (seconds // 60, seconds % 60)


def _user_cards(usernames):
    """Nombre visible e imagen de perfil de cada evaluador (por nombre de usuario)."""
    from django.contrib.auth.models import User
    cards = {}
    for u in User.objects.filter(username__in=[n for n in usernames if n]).select_related('evaluator_profile'):
        try:
            image = u.evaluator_profile.image_url
        except EvaluatorProfile.DoesNotExist:
            image = ''
        cards[u.username] = {'name': u.get_full_name() or u.username, 'image': image}
    return cards


@staff_member_required
def dashboard(request):
    stats = get_stats()
    videos = get_uploaded_videos()
    evaluaciones = {(ev.payment_id, ev.task_id): ev for ev in Evaluacion.objects.all()}
    campaigns = {p.payment_id: p.campId for p in SubjectProfile.objects.all()}
    tasks = {t.task_id: t.task_description for t in TasksDescription.objects.all()}

    status_counts = {k: 0 for k, _, _ in VIDEO_STATES}
    by_campaign, by_task = {}, {}
    for v in videos:
        ev = evaluaciones.get((v['payment_id'], v['task_id']))
        state = 'completed' if ev and ev.completada else 'in_progress' if ev else 'pending'
        status_counts[state] += 1
        for groups, key in ((by_campaign, campaigns.get(v['payment_id']) or ''), (by_task, v['task_id'])):
            groups.setdefault(key, {k: 0 for k, _, _ in VIDEO_STATES})[state] += 1

    progress_total, progress_segments = _donut(status_counts, [k for k, _, _ in VIDEO_STATES])

    severity_counts = {}
    for sev in ProblemaIdentificado.objects.values_list('severidad', flat=True):
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    severity_total, severity_segments = _donut(severity_counts, [k for k, _ in SEVERITIES])

    indicator_counts = {}
    for ind in Anotacion.objects.values_list('indicador', flat=True):
        indicator_counts[ind] = indicator_counts.get(ind, 0) + 1
    top_indicators = sorted(indicator_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    top_value = top_indicators[0][1] if top_indicators else 1

    completed = Evaluacion.objects.filter(completada=True)
    recientes = list(Evaluacion.objects.order_by(F('fecha_fin').desc(nulls_last=True), '-fecha_inicio', '-id')[:6])
    cards = _user_cards([ev.evaluador for ev in recientes])
    workers = {p.payment_id: p.workerId for p in SubjectProfile.objects.all()}
    activity = [
        {'ev': ev, 'worker': workers.get(ev.payment_id, ev.payment_id[:12]),
         'card': cards.get(ev.evaluador, {'name': ev.evaluador or '—', 'image': ''}),
         'when': ev.fecha_fin or ev.fecha_inicio}
        for ev in recientes
    ]
    active_seconds = [ev.tiempo_activo_segundos for ev in completed]

    context = {
        'active_page': 'dashboard',
        'stats': stats,
        'video_states': VIDEO_STATES,
        'severities': SEVERITIES,
        'progress_total': progress_total,
        'progress_segments': progress_segments,
        'progress_legend': [{'key': k, 'label': label, 'icon': icon, 'value': status_counts[k]}
                            for k, label, icon in VIDEO_STATES],
        'progress_pct': round(100.0 * status_counts['completed'] / progress_total) if progress_total else 0,
        'severity_total': severity_total,
        'severity_segments': severity_segments,
        'severity_legend': [{'key': k.lower(), 'label': k, 'icon': icon, 'value': severity_counts.get(k, 0)}
                            for k, icon in SEVERITIES],
        'campaign_rows': _stacked_rows(by_campaign, lambda k: k),
        'task_rows': _stacked_rows(by_task, lambda k: k),
        'task_descriptions': tasks,
        'top_indicators': [{'code': c, 'value': n, 'width': round(100.0 * n / top_value)} for c, n in top_indicators],
        'activity': activity,
        'total_annotations': Anotacion.objects.count(),
        'total_problems': ProblemaIdentificado.objects.count(),
        'avg_time': _format_duration(sum(active_seconds) / len(active_seconds)) if active_seconds else '—',
    }
    return render(request, 'evaluation/dashboard.html', context)


def get_uploaded_videos():
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    videos = []
    if not os.path.exists(base_dir):
        return videos

    profiles = {p.payment_id: p.workerId for p in SubjectProfile.objects.all()}

    for payment_id in os.listdir(base_dir):
        payment_path = os.path.join(base_dir, payment_id)
        if not os.path.isdir(payment_path):
            continue
        for task_id in os.listdir(payment_path):
            task_path = os.path.join(payment_path, task_id)
            if not os.path.isdir(task_path):
                continue
            for date_folder in os.listdir(task_path):
                date_path = os.path.join(task_path, date_folder)
                if not os.path.isdir(date_path):
                    continue
                for filename in os.listdir(date_path):
                    if filename.endswith('.webm'):
                        videos.append({
                            'payment_id': payment_id,
                            'worker_id': profiles.get(payment_id, payment_id),
                            'task_id': task_id,
                            'date': date_folder,
                            'filename': filename,
                        })
    return videos


@staff_member_required
def lista_videos(request):
    videos = get_uploaded_videos()

    evaluaciones_map = {}
    for ev in Evaluacion.objects.all():
        evaluaciones_map[f"{ev.payment_id}_{ev.task_id}"] = ev

    for v in videos:
        ev = evaluaciones_map.get(f"{v['payment_id']}_{v['task_id']}")
        v['evaluada'] = ev is not None and ev.completada
        v['en_progreso'] = ev is not None and not ev.completada

    filtro = request.GET.get('filtro', 'todos')
    if filtro == 'pendientes':
        videos = [v for v in videos if not v.get('evaluada')]
    elif filtro == 'completadas':
        videos = [v for v in videos if v.get('evaluada')]
    elif filtro == 'en_progreso':
        videos = [v for v in videos if v.get('en_progreso')]

    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        q = busqueda.lower()
        videos = [v for v in videos if q in v['worker_id'].lower() or q in v['payment_id'].lower()]

    campana = request.GET.get('camp', '').strip()
    if campana:
        en_campana = set(SubjectProfile.objects.filter(campId=campana).values_list('payment_id', flat=True))
        videos = [v for v in videos if v['payment_id'] in en_campana]

    total_videos = len(get_uploaded_videos())
    total_evaluated = Evaluacion.objects.filter(completada=True).count()
    total_pending = total_videos - total_evaluated

    context = {
        'active_page': 'videos',
        'videos': videos,
        'filtro': filtro,
        'busqueda': busqueda,
        'campana': campana,
        'stats': get_stats(),
    }
    return render(request, 'evaluation/lista_videos.html', context)


@staff_member_required
def evaluar_video(request, payment_id, task_id):
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    video_files = []

    task_path = os.path.join(base_dir, payment_id, task_id)
    if os.path.exists(task_path):
        for date_folder in os.listdir(task_path):
            date_path = os.path.join(task_path, date_folder)
            if os.path.isdir(date_path):
                for f in os.listdir(date_path):
                    if f.endswith('.webm'):
                        video_files.append({
                            'filename': f,
                            'date': date_folder,
                            'url': f'/admin-panel/video/{payment_id}/{task_id}/{date_folder}/{f}',
                        })

    if not video_files:
        raise Http404("No videos found for this worker/task")

    evaluacion, created = Evaluacion.objects.get_or_create(
        payment_id=payment_id,
        task_id=task_id,
        defaults={
            'video_id': video_files[0]['filename'],
        }
    )

    # annotation_start_time: la primera vez que alguien abre el video para evaluarlo
    cambios = []
    if not evaluacion.fecha_inicio:
        evaluacion.fecha_inicio = timezone.now()
        cambios.append('fecha_inicio')
    if not evaluacion.evaluador:
        evaluacion.evaluador = request.user.get_username()
        cambios.append('evaluador')
    if cambios:
        evaluacion.save(update_fields=cambios)

    try:
        profile = SubjectProfile.objects.get(payment_id=payment_id)
        worker_id = profile.workerId
    except SubjectProfile.DoesNotExist:
        worker_id = payment_id

    evaluacion.video = video_label(evaluacion.video_id)

    context = {
        'active_page': 'videos',
        'evaluacion': evaluacion,
        'payment_id': payment_id,
        'worker_id': worker_id,
        'task_id': task_id,
        'video_files': video_files,
        'video_label': evaluacion.video,
        'evaluacion_lista': [evaluacion],
        'stats': get_stats(),
    }
    return render(request, 'evaluation/evaluar_video.html', context)


def get_stats():
    videos = get_uploaded_videos()
    return {
        'total': len(videos),
        'evaluados': Evaluacion.objects.filter(completada=True).count(),
        'pendientes': len(videos) - Evaluacion.objects.filter(completada=True).count(),
        'campanas': Test_Input.objects.exclude(campId=DEMO_CAMP_ID).count(),
    }


@staff_member_required
def campanas(request):
    """Videos de los participantes que entraron con un enlace de campaña, en una tabla
    como la de Videos (con la campaña de cada uno) y su estado, sin el botón de evaluar."""
    evaluaciones = {(ev.payment_id, ev.task_id): ev for ev in Evaluacion.objects.all()}
    # Solo participantes que entraron con un enlace de campaña (no los del enlace por defecto)
    perfiles = (SubjectProfile.objects.exclude(campId__isnull=True).exclude(campId='')
                .exclude(campId=DEMO_CAMP_ID).order_by('campId', 'workerId'))

    videos_por_pago = {}
    for v in get_uploaded_videos():
        ev = evaluaciones.get((v['payment_id'], v['task_id']))
        v['evaluada'] = ev is not None and ev.completada
        v['en_progreso'] = ev is not None and not ev.completada
        videos_por_pago.setdefault(v['payment_id'], []).append(v)

    filas = []
    for p in perfiles:
        videos = sorted(videos_por_pago.get(p.payment_id, []), key=lambda v: (v['task_id'], v['date']))
        for v in videos:
            filas.append(dict(v, camp_id=p.campId))
        if not videos:
            # Participante registrado que aún no sube videos: se muestra para poder copiar su Worker ID
            filas.append({'camp_id': p.campId, 'worker_id': p.workerId, 'payment_id': p.payment_id,
                          'sin_video': True, 'evaluada': False, 'en_progreso': False})

    filtro = request.GET.get('filtro', 'todos')
    busqueda = request.GET.get('q', '').strip()
    if filtro == 'pendientes':
        filas = [f for f in filas if not f['evaluada'] and not f['en_progreso']]
    elif filtro == 'en_progreso':
        filas = [f for f in filas if f['en_progreso']]
    elif filtro == 'completadas':
        filas = [f for f in filas if f['evaluada']]
    if busqueda:
        # Por ID de campaña, Worker ID o ID del archivo
        q = busqueda.lower()
        filas = [f for f in filas if q in f['camp_id'].lower() or q in f['worker_id'].lower()
                 or q in f['payment_id'].lower()]

    context = {
        'active_page': 'campanas',
        'videos': filas,
        'filtro': filtro,
        'busqueda': busqueda,
        'stats': get_stats(),
    }
    return render(request, 'evaluation/campanas.html', context)


@staff_member_required
def crear_campana(request):
    if request.method == 'POST':
        form = Test_InputForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Campaign created successfully.')
                return redirect('admin_campanas')
            except IntegrityError:
                form.add_error('campId', 'A campaign with this ID already exists.')
    else:
        form = Test_InputForm()

    context = {
        'active_page': 'campanas',
        'form': form,
        'stats': get_stats(),
    }
    return render(request, 'evaluation/crear_campana.html', context)


@staff_member_required
def audio_report(request):
    """Grabaciones .webm de cada worker/task, para escuchar su audio o descargarlas."""
    grabaciones = get_uploaded_videos()
    total = len(grabaciones)

    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        q = busqueda.lower()
        grabaciones = [g for g in grabaciones
                       if q in g['worker_id'].lower() or q in g['payment_id'].lower() or q in g['task_id'].lower()]

    # Más recientes primero; dentro del mismo día, por worker y task
    grabaciones.sort(key=lambda g: (g['worker_id'], g['task_id']))
    grabaciones.sort(key=lambda g: g['date'], reverse=True)

    context = {
        'active_page': 'audio_report',
        'grabaciones': grabaciones,
        'total_grabaciones': total,
        'busqueda': busqueda,
        'stats': get_stats(),
    }
    return render(request, 'evaluation/audio_report.html', context)


def _datos_tabla_anotaciones(request):
    """Datos de la Tabla de anotaciones (los usan la página y la descarga en Excel)."""
    evaluaciones = Evaluacion.objects.order_by('payment_id', 'task_id')
    seleccion = request.GET.get('video', '')
    if seleccion.isdigit():
        evaluaciones = evaluaciones.filter(id=int(seleccion))

    anotaciones = (Anotacion.objects.filter(evaluacion__in=evaluaciones)
                   .select_related('evaluacion', 'problema_ref')
                   .order_by('evaluacion__payment_id', 'evaluacion__task_id', 'start_time', 'id'))
    problemas = (ProblemaIdentificado.objects.filter(evaluacion__in=evaluaciones)
                 .select_related('evaluacion', 'problema')
                 .order_by('evaluacion__payment_id', 'evaluacion__task_id', 'problema__codigo'))

    for a in anotaciones:
        a.video = video_label(a.evaluacion.video_id)
    for p in problemas:
        p.video = video_label(p.evaluacion.video_id)

    # Resumen por video: cuantas veces aparece cada problema y promedio por problema
    anot_por_eval, prob_por_eval = {}, {}
    for a in anotaciones:
        anot_por_eval.setdefault(a.evaluacion_id, []).append(a)
    for p in problemas:
        prob_por_eval.setdefault(p.evaluacion_id, []).append(p)

    resumen_videos = []
    for ev in evaluaciones:
        filas, totales = resumen_problemas(anot_por_eval.get(ev.id, []), prob_por_eval.get(ev.id, []))
        if not filas:
            continue
        resumen_videos.append({
            'evaluacion': ev,
            'video': video_label(ev.video_id),
            'filas': filas,
            'totales': totales,
        })

    tiempos = [ev for ev in evaluaciones if ev.fecha_inicio]
    for ev in tiempos:
        ev.video = video_label(ev.video_id)

    return {
        'anotaciones': anotaciones,
        'problemas': problemas,
        'resumen_videos': resumen_videos,
        'tiempos': tiempos,
        'seleccion': seleccion,
    }


@staff_member_required
def tabla_anotaciones(request):
    """Vista tipo Excel: 1. Annotation table, 2. Problem table y resumen de problemas por video."""
    context = _datos_tabla_anotaciones(request)
    context.update({
        'active_page': 'tabla',
        'todas_evaluaciones': Evaluacion.objects.order_by('payment_id', 'task_id'),
        'stats': get_stats(),
    })
    return render(request, 'evaluation/tabla_anotaciones.html', context)


@staff_member_required
def tabla_anotaciones_excel(request):
    """Descarga la Tabla de anotaciones en .xlsx, con una hoja por cada pestaña de la página.
    Respeta el filtro de video (?video=<id>)."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    datos = _datos_tabla_anotaciones(request)

    head_font = Font(bold=True, color='FFFFFF')
    head_fill = PatternFill('solid', fgColor='2563EB')
    title_font = Font(bold=True, size=12)
    muted_font = Font(color='6B7280')
    thin = Side(style='thin', color='E5E7EB')
    cell_border = Border(bottom=thin)
    wrap = Alignment(wrap_text=True, vertical='top')
    top = Alignment(vertical='top')

    def write_header(ws, row, headers):
        for col, title in enumerate(headers, start=1):
            c = ws.cell(row=row, column=col, value=title)
            c.font = head_font
            c.fill = head_fill
            c.alignment = Alignment(vertical='center')

    def write_rows(ws, start_row, rows, wrap_cols=()):
        r = start_row
        for values in rows:
            for col, value in enumerate(values, start=1):
                c = ws.cell(row=r, column=col, value=value)
                c.border = cell_border
                c.alignment = wrap if col in wrap_cols else top
            r += 1
        return r

    def set_widths(ws, widths):
        for col, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(col)].width = width

    def local(dt):
        return timezone.localtime(dt).replace(tzinfo=None) if dt else None

    def table_sheet(ws, headers, rows, widths, wrap_cols=(), empty='No data yet.'):
        write_header(ws, 1, headers)
        if rows:
            last = write_rows(ws, 2, rows, wrap_cols)
            ws.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(headers)), last - 1)
        else:
            ws.cell(row=2, column=1, value=empty).font = muted_font
        ws.freeze_panes = 'A2'
        set_widths(ws, widths)

    wb = Workbook()

    # 1. Annotation table (mismas columnas que la página)
    ws = wb.active
    ws.title = '1. Annotation table'
    table_sheet(ws,
                ['video_id', 'start_time', 'finish_time', 'indicator_code', 'task_moment', 'problem', 'comments'],
                [[a.video, a.start_time, a.finish_time, a.indicador, a.contexto, a.problema, a.comentarios]
                 for a in datos['anotaciones']],
                [34, 11, 11, 15, 24, 44, 44], wrap_cols=(6, 7), empty='No annotations yet.')

    # 2. Problem table
    ws = wb.create_sheet('2. Problem table')
    table_sheet(ws,
                ['video_id', 'code', 'problem', 'severity', 'type', 'comment'],
                [[p.video, p.problema.codigo, p.problema.descripcion, p.severidad, p.tipo, p.comentarios]
                 for p in datos['problemas']],
                [34, 11, 44, 12, 15, 44], wrap_cols=(3, 6), empty='No problems registered yet.')

    # 3. Time annotation
    ws = wb.create_sheet('3. Time annotation')
    table_sheet(ws,
                ['video_id', 'annotation_start_time', 'annotation_finish_time', 'duration', 'active_time', 'evaluator'],
                [[ev.video, local(ev.fecha_inicio), local(ev.fecha_fin) or 'In progress',
                  ev.duracion_texto or '-', ev.tiempo_activo_texto, ev.evaluador or '-']
                 for ev in datos['tiempos']],
                [34, 22, 22, 12, 12, 18], empty='No video has been opened for evaluation yet.')
    for cells in ws.iter_rows(min_row=2, min_col=2, max_col=3):
        for c in cells:
            if c.value and not isinstance(c.value, str):
                c.number_format = 'yyyy-mm-dd hh:mm'

    # Problem summary: un bloque por video, como las tarjetas de la página
    ws = wb.create_sheet('Problem summary')
    headers = ['code', 'problem', 'severity', 'type', 'occurrences', '% of annotations', 'avg duration (s)']
    row = 1
    if not datos['resumen_videos']:
        ws.cell(row=1, column=1, value='No annotations yet.').font = muted_font
    for r in datos['resumen_videos']:
        ws.cell(row=row, column=1, value='Video: %s \u00b7 Task %s' % (r['video'], r['evaluacion'].task_id)).font = title_font
        row += 1
        t = r['totales']
        for label, value in (('Annotations', t['anotaciones']),
                             ('Distinct problems', t['problemas_distintos']),
                             ('Average occurrences per problem', t['promedio_por_problema'])):
            ws.cell(row=row, column=1, value=label).font = muted_font
            ws.cell(row=row, column=2, value=value)
            row += 1
        write_header(ws, row, headers)
        first = row + 1
        row = write_rows(ws, first, [
            [f['codigo'], f['descripcion'], f['severidad'] or '-', f['tipo'] or '-', f['ocurrencias'],
             (f['porcentaje'] or 0) / 100.0,
             f['duracion_promedio'] if f['duracion_promedio'] is not None else '-']
            for f in r['filas']], wrap_cols=(2,))
        for cells in ws.iter_rows(min_row=first, max_row=row - 1, min_col=6, max_col=6):
            cells[0].number_format = '0.0%'
        row += 1  # línea en blanco entre videos
    set_widths(ws, [14, 44, 12, 15, 13, 17, 17])

    output = BytesIO()
    wb.save(output)
    nombre = 'annotation_table'
    if datos['seleccion']:
        videos = [ev.video for ev in datos['tiempos']] or [a.video for a in datos['anotaciones']]
        if videos:
            nombre += '_' + videos[0][:40]
    nombre += '_%s.xlsx' % timezone.localdate().isoformat()
    response = HttpResponse(output.getvalue(),
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="%s"' % nombre
    return response


@staff_member_required
def guia_evaluacion(request):
    context = {
        'active_page': 'guia',
        'stats': get_stats(),
    }
    return render(request, 'evaluation/guia.html', context)


SETTINGS_TABS = ('account', 'preferences', 'shortcuts')
PASSWORD_FIELDS = ('old_password', 'new_password1', 'new_password2')


@staff_member_required
def config_panel(request):
    """Configuración: un solo formulario guarda cuenta, preferencias y atajos a la vez."""
    profile, _ = EvaluatorProfile.objects.get_or_create(user=request.user)
    shortcut_initial = {'key_' + a: k for a, k in resolve_shortcuts(profile).items()}
    shortcut_initial['shortcuts_enabled'] = profile.shortcuts_enabled

    with translation.override(profile.language):
        if request.method == 'POST':
            account_form = AccountForm(request.POST, request.FILES, instance=request.user)
            preferences_form = PreferencesForm(request.POST)
            shortcuts_form = ShortcutsForm(request.POST)
            # La contraseña solo se valida si el usuario escribió algo en esos campos
            wants_password = any(request.POST.get(f) for f in PASSWORD_FIELDS)
            password_form = (PasswordChangeForm(request.user, request.POST) if wants_password
                             else PasswordChangeForm(request.user))

            forms_ok = {
                'account': account_form.is_valid() and (not wants_password or password_form.is_valid()),
                'preferences': preferences_form.is_valid(),
                'shortcuts': shortcuts_form.is_valid(),
            }
            if all(forms_ok.values()):
                account_form.save()
                photo = account_form.cleaned_data.get('photo')
                avatar_url = account_form.cleaned_data.get('avatar_url')
                if photo:
                    profile.photo, profile.avatar_url = photo, ''
                elif avatar_url and avatar_url != profile.avatar_url:
                    profile.photo, profile.avatar_url = None, avatar_url
                profile.language = preferences_form.cleaned_data['language']
                profile.accent_color = preferences_form.cleaned_data['accent_color']
                profile.shortcuts = shortcuts_form.shortcut_keys()
                profile.shortcuts_enabled = shortcuts_form.cleaned_data['shortcuts_enabled']
                profile.save()
                if wants_password:
                    password_form.save()
                    update_session_auth_hash(request, password_form.user)  # no cerrar la sesión actual
                messages.success(request, translate('Settings saved.', profile.language))
                tab = request.POST.get('tab')
                return redirect('/admin-panel/config/?tab=' + (tab if tab in SETTINGS_TABS else 'account'))
            # Abrir la primera pestaña que tenga errores
            active_tab = next(t for t in SETTINGS_TABS if not forms_ok[t])
        else:
            account_form = AccountForm(instance=request.user, initial={
                'avatar_url': '' if profile.photo else profile.avatar_url,
            })
            password_form = PasswordChangeForm(request.user)
            preferences_form = PreferencesForm(initial={
                'language': profile.language,
                'accent_color': profile.accent_color,
            })
            shortcuts_form = ShortcutsForm(initial=shortcut_initial)
            active_tab = request.GET.get('tab')
            active_tab = active_tab if active_tab in SETTINGS_TABS else 'account'

        context = {
            'active_page': 'config',
            'active_tab': active_tab,
            'profile': profile,
            'account_form': account_form,
            'password_form': password_form,
            'preferences_form': preferences_form,
            'shortcuts_form': shortcuts_form,
            'shortcut_rows': [
                {'action': action, 'name': name, 'help': help_text, 'icon': icon,
                 'key': shortcuts_form['key_' + action].value(),
                 'label': shortcut_label(shortcuts_form['key_' + action].value() or default),
                 'default': default, 'errors': shortcuts_form['key_' + action].errors}
                for action, name, help_text, default, icon in SHORTCUT_ACTIONS
            ],
            'shortcut_key_labels': NAMED_KEYS,
            'languages': LANGUAGES,
            'accent_colors': [
                {'key': key, 'name': name, 'light': light, 'style': accent_style(accent_palette(light, dark))}
                for key, name, light, dark in ACCENT_COLORS
            ],
            'stats': get_stats(),
        }
        return render(request, 'evaluation/config.html', context,
                      status=400 if request.method == 'POST' else 200)


@staff_member_required
def serve_video(request, payment_id, task_id, date_folder, filename):
    base_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), 'uploads'))
    filepath = os.path.realpath(os.path.join(base_dir, payment_id, task_id, date_folder, filename))

    # Evita salir de la carpeta uploads con rutas tipo ".."
    if not filepath.startswith(base_dir + os.sep) or not os.path.isfile(filepath):
        raise Http404("Video not found")

    # ?download=1 -> descarga el archivo; si no, se reproduce en el navegador
    descargar = request.GET.get('download') == '1'
    response = FileResponse(open(filepath, 'rb'), content_type='video/webm',
                            as_attachment=descargar, filename=filename)
    if not descargar:
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


def video_label(filename):
    """Nombre del video como aparece en la columna video_id del Excel (sin extension)."""
    return os.path.splitext(filename or '')[0]


def anotacion_dict(a):
    return {
        'id': a.id,
        'start_time': a.start_time,
        'finish_time': a.finish_time,
        'indicador': a.indicador,
        'contexto': a.contexto,
        'problema': a.problema,
        'problema_id': a.problema_ref_id,
        'comentarios': a.comentarios,
    }


def problema_dict(p):
    return {
        'id': p.id,
        'problema_id': p.problema_id,
        'codigo': p.problema.codigo,
        'descripcion': p.problema.descripcion,
        'severidad': p.severidad,
        'tipo': p.tipo,
        'comentarios': p.comentarios,
    }


def identificar_problema(evaluacion, catalogo_item):
    """Asegura que el problema del catalogo figure en los problemas identificados del video.
    Si es nuevo en este video, copia severidad y tipo de su ultimo registro en otro video.
    Devuelve el ProblemaIdentificado creado, o None si ya estaba (o no hay problema)."""
    if catalogo_item is None:
        return None
    if evaluacion.problemas.filter(problema=catalogo_item).exists():
        return None
    previo = (ProblemaIdentificado.objects.filter(problema=catalogo_item)
              .order_by('-fecha_creacion', '-id').first())
    return ProblemaIdentificado.objects.create(
        evaluacion=evaluacion,
        problema=catalogo_item,
        severidad=previo.severidad if previo else '',
        tipo=previo.tipo if previo else '',
    )


def resumen_problemas(anotaciones, problemas_identificados=()):
    """
    Cuenta cuantas veces aparece cada problema en un conjunto de anotaciones.
    Devuelve (filas, totales). Cada fila: codigo, descripcion, severidad, tipo,
    ocurrencias, porcentaje y duracion promedio (segundos).
    """
    clasificacion = {p.problema_id: p for p in problemas_identificados}
    grupos = {}
    for a in anotaciones:
        key = a.problema_ref_id or ('txt', a.problema.strip().lower())
        g = grupos.setdefault(key, {
            'codigo': a.problema_ref.codigo if a.problema_ref_id else '',
            'descripcion': a.problema or '(no problem)',
            'ocurrencias': 0,
            'duraciones': [],
        })
        g['ocurrencias'] += 1
        dur = a.duracion_segundos()
        if dur is not None:
            g['duraciones'].append(dur)

    total = sum(g['ocurrencias'] for g in grupos.values())
    filas = []
    for key, g in grupos.items():
        pi = clasificacion.get(key)
        durs = g.pop('duraciones')
        g['severidad'] = pi.severidad if pi else ''
        g['tipo'] = pi.tipo if pi else ''
        g['porcentaje'] = round(100.0 * g['ocurrencias'] / total, 1) if total else 0
        g['duracion_promedio'] = round(sum(durs) / len(durs), 1) if durs else None
        filas.append(g)
    filas.sort(key=lambda f: (-f['ocurrencias'], f['codigo']))

    distintos = len(filas)
    totales = {
        'anotaciones': total,
        'problemas_distintos': distintos,
        'promedio_por_problema': round(total / distintos, 2) if distintos else 0,
    }
    return filas, totales


def validar_tiempos(start, finish):
    if parse_mmss(start) is None:
        return 'Start time must use the MM:SS format.'
    if finish and parse_mmss(finish) is None:
        return 'Finish time must use the MM:SS format (or be empty).'
    if finish and parse_mmss(finish) < parse_mmss(start):
        return 'Finish time cannot be before start time.'
    return None


def leer_json(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return None


@staff_member_required
def api_cargar_datos(request, evaluacion_id):
    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    anotaciones = [anotacion_dict(a) for a in evaluacion.anotaciones.all()]
    problemas = [problema_dict(p) for p in evaluacion.problemas.select_related('problema')]
    return JsonResponse({
        'anotaciones': anotaciones,
        'problemas': problemas,
    })


@staff_member_required
def api_agregar_anotacion(request, evaluacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    data = leer_json(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    catalogo_item = None
    if data.get('problema_id'):
        catalogo_item = get_object_or_404(CatalogoProblema, id=data['problema_id'])

    anotacion = Anotacion.objects.create(
        evaluacion=evaluacion,
        start_time=data.get('start_time', '00:00'),
        finish_time=data.get('finish_time', '00:00'),
        indicador=data.get('indicador', ''),
        contexto=data.get('contexto', ''),
        problema=data.get('problema', ''),
        problema_ref=catalogo_item,
        comentarios=data.get('comentarios', ''),
    )
    nuevo = identificar_problema(evaluacion, catalogo_item)
    return JsonResponse({
        'id': anotacion.id,
        'ok': True,
        'anotacion': anotacion_dict(anotacion),
        'problema': problema_dict(nuevo) if nuevo else None,
    })


@staff_member_required
def api_editar_anotacion(request, anotacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    anotacion = get_object_or_404(Anotacion, id=anotacion_id)
    data = leer_json(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    start = (data.get('start_time', anotacion.start_time) or '').strip()
    finish = (data.get('finish_time', anotacion.finish_time) or '').strip()
    error = validar_tiempos(start, finish)
    if error:
        return JsonResponse({'error': error}, status=400)

    if 'problema_id' in data:
        if data['problema_id']:
            anotacion.problema_ref = get_object_or_404(CatalogoProblema, id=data['problema_id'])
        else:
            anotacion.problema_ref = None
            anotacion.problema = ''
    anotacion.start_time = start
    anotacion.finish_time = finish
    anotacion.indicador = data.get('indicador', anotacion.indicador)
    anotacion.contexto = data.get('contexto', anotacion.contexto)
    anotacion.comentarios = data.get('comentarios', anotacion.comentarios)
    anotacion.save()
    nuevo = identificar_problema(anotacion.evaluacion, anotacion.problema_ref)
    return JsonResponse({
        'ok': True,
        'anotacion': anotacion_dict(anotacion),
        'problema': problema_dict(nuevo) if nuevo else None,
    })


@staff_member_required
def api_eliminar_anotacion(request, anotacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    anotacion = get_object_or_404(Anotacion, id=anotacion_id)
    anotacion.delete()
    return JsonResponse({'ok': True})


@staff_member_required
def api_catalogo_problemas(request):
    catalogo = list(CatalogoProblema.objects.order_by('codigo').values('id', 'codigo', 'descripcion'))
    return JsonResponse({'catalogo': catalogo})


@staff_member_required
def api_crear_problema(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    descripcion = (data.get('descripcion') or '').strip()
    if not descripcion:
        return JsonResponse({'error': 'Description is required'}, status=400)

    catalogo_item = CatalogoProblema.objects.create(descripcion=descripcion)
    return JsonResponse({
        'id': catalogo_item.id,
        'codigo': catalogo_item.codigo,
        'descripcion': catalogo_item.descripcion,
        'ok': True,
    })


@staff_member_required
def api_agregar_problema(request, evaluacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    data = json.loads(request.body)

    if not data.get('problema_id'):
        return JsonResponse({'error': 'problema_id is required'}, status=400)

    catalogo_item = get_object_or_404(CatalogoProblema, id=data.get('problema_id'))

    problema = ProblemaIdentificado.objects.create(
        evaluacion=evaluacion,
        problema=catalogo_item,
        severidad=data.get('severidad', ''),
        tipo=data.get('tipo', ''),
        comentarios=data.get('comentarios', ''),
    )
    return JsonResponse({
        'id': problema.id,
        'codigo': catalogo_item.codigo,
        'descripcion': catalogo_item.descripcion,
        'ok': True,
        'problema': problema_dict(problema),
    })


@staff_member_required
def api_editar_problema(request, problema_id):
    """Corrige un problema identificado: severidad, tipo, comentarios, problema del catalogo
    y opcionalmente el texto del problema en el catalogo (se actualiza en todas sus anotaciones)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    problema = get_object_or_404(ProblemaIdentificado.objects.select_related('problema'), id=problema_id)
    data = leer_json(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    nuevo_id = data.get('problema_id')
    if nuevo_id and str(nuevo_id) != str(problema.problema_id):
        nuevo = get_object_or_404(CatalogoProblema, id=nuevo_id)
        # Las anotaciones de este video que apuntaban al problema anterior pasan al nuevo
        Anotacion.objects.filter(evaluacion=problema.evaluacion, problema_ref=problema.problema).update(
            problema_ref=nuevo, problema=nuevo.descripcion)
        problema.problema = nuevo

    descripcion = (data.get('descripcion') or '').strip()
    if descripcion and descripcion != problema.problema.descripcion:
        catalogo_item = problema.problema
        catalogo_item.descripcion = descripcion
        catalogo_item.save()
        catalogo_item.anotaciones.update(problema=descripcion)

    problema.severidad = data.get('severidad', problema.severidad)
    problema.tipo = data.get('tipo', problema.tipo)
    problema.comentarios = data.get('comentarios', problema.comentarios)
    problema.save()
    return JsonResponse({'ok': True, 'problema': problema_dict(problema)})


@staff_member_required
def api_eliminar_problema(request, problema_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    problema = get_object_or_404(ProblemaIdentificado, id=problema_id)
    problema.delete()
    return JsonResponse({'ok': True})


@staff_member_required
def api_completar_evaluacion(request, evaluacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    data = json.loads(request.body)

    evaluacion.completada = True
    evaluacion.fecha_fin = timezone.now()
    evaluacion.evaluador = evaluacion.evaluador or request.user.get_username()
    evaluacion.observaciones_generales = data.get('observaciones', '')
    evaluacion.save()
    return JsonResponse({'ok': True})


# Tope por envio: el navegador reporta cada 30 s, asi un cliente roto no puede inflar el tiempo
MAX_SEGUNDOS_POR_ENVIO = 120


@staff_member_required
def api_registrar_tiempo(request, evaluacion_id):
    """Suma tiempo activo de anotacion. Recibe form-data (compatible con navigator.sendBeacon)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        segundos = int(request.POST.get('segundos', 0))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'segundos must be an integer'}, status=400)
    segundos = max(0, min(segundos, MAX_SEGUNDOS_POR_ENVIO))

    get_object_or_404(Evaluacion, id=evaluacion_id)
    Evaluacion.objects.filter(id=evaluacion_id).update(
        tiempo_activo_segundos=F('tiempo_activo_segundos') + segundos)
    evaluacion = Evaluacion.objects.get(id=evaluacion_id)
    return JsonResponse({'ok': True, 'tiempo_activo_segundos': evaluacion.tiempo_activo_segundos})
