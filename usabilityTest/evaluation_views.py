import os
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, Http404, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import F, Q
from django.utils import timezone

from .models import (Evaluacion, Anotacion, ProblemaIdentificado, CatalogoProblema, SubjectProfile, Test_Input,
                     parse_mmss)
from .forms import Test_InputForm


@staff_member_required
def dashboard(request):
    stats = get_stats()
    evaluaciones_recientes = Evaluacion.objects.all().order_by('-id')[:5]

    context = {
        'active_page': 'dashboard',
        'stats': stats,
        'evaluaciones_recientes': evaluaciones_recientes,
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
        videos = [v for v in videos if busqueda.lower() in v['worker_id'].lower()]

    total_videos = len(get_uploaded_videos())
    total_evaluated = Evaluacion.objects.filter(completada=True).count()
    total_pending = total_videos - total_evaluated

    context = {
        'active_page': 'videos',
        'videos': videos,
        'filtro': filtro,
        'busqueda': busqueda,
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
        'campanas': Test_Input.objects.count(),
    }


@staff_member_required
def campanas(request):
    context = {
        'active_page': 'campanas',
        'campanas_list': Test_Input.objects.all(),
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
def reportes(request):
    videos = get_uploaded_videos()
    evaluaciones = Evaluacion.objects.filter(completada=True)

    total_anotaciones = 0
    total_problemas = 0
    for ev in evaluaciones:
        total_anotaciones += ev.anotaciones.count() if hasattr(ev, 'anotaciones') else 0
        total_problemas += ev.problemas.count() if hasattr(ev, 'problemas') else 0

    context = {
        'active_page': 'reportes',
        'total_evaluaciones': evaluaciones.count(),
        'total_videos': len(videos),
        'total_anotaciones': total_anotaciones,
        'total_problemas': total_problemas,
        'evaluaciones': evaluaciones,
        'stats': get_stats(),
    }
    return render(request, 'evaluation/reportes.html', context)


@staff_member_required
def tabla_anotaciones(request):
    """Vista tipo Excel: 1. Annotation table, 2. Problem table y resumen de problemas por video."""
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

    context = {
        'active_page': 'tabla',
        'anotaciones': anotaciones,
        'problemas': problemas,
        'resumen_videos': resumen_videos,
        'tiempos': tiempos,
        'todas_evaluaciones': Evaluacion.objects.order_by('payment_id', 'task_id'),
        'seleccion': seleccion,
        'stats': get_stats(),
    }
    return render(request, 'evaluation/tabla_anotaciones.html', context)


@staff_member_required
def guia_evaluacion(request):
    context = {
        'active_page': 'guia',
        'stats': get_stats(),
    }
    return render(request, 'evaluation/guia.html', context)


@staff_member_required
def config_panel(request):
    context = {
        'active_page': 'config',
        'stats': get_stats(),
    }
    return render(request, 'evaluation/config.html', context)


@staff_member_required
def serve_video(request, payment_id, task_id, date_folder, filename):
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    filepath = os.path.join(base_dir, payment_id, task_id, date_folder, filename)

    if not os.path.exists(filepath):
        raise Http404("Video not found")

    response = FileResponse(open(filepath, 'rb'), content_type='video/webm')
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
