import os
import json
from django.shortcuts import render, get_object_or_404
from django.http import FileResponse, Http404, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.utils import timezone

from .models import Evaluacion, Anotacion, ProblemaIdentificado, SubjectProfile, Test_Input


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

    try:
        profile = SubjectProfile.objects.get(payment_id=payment_id)
        worker_id = profile.workerId
    except SubjectProfile.DoesNotExist:
        worker_id = payment_id

    context = {
        'active_page': 'videos',
        'evaluacion': evaluacion,
        'payment_id': payment_id,
        'worker_id': worker_id,
        'task_id': task_id,
        'video_files': video_files,
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


@staff_member_required
def api_cargar_datos(request, evaluacion_id):
    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    anotaciones = list(evaluacion.anotaciones.values(
        'id', 'start_time', 'finish_time', 'indicador', 'contexto', 'problema', 'comentarios'
    ))
    problemas = list(evaluacion.problemas.values(
        'id', 'descripcion', 'severidad', 'tipo', 'comentarios'
    ))
    return JsonResponse({
        'anotaciones': anotaciones,
        'problemas': problemas,
    })


@staff_member_required
def api_agregar_anotacion(request, evaluacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    data = json.loads(request.body)

    anotacion = Anotacion.objects.create(
        evaluacion=evaluacion,
        start_time=data.get('start_time', '00:00'),
        finish_time=data.get('finish_time', '00:00'),
        indicador=data.get('indicador', ''),
        contexto=data.get('contexto', ''),
        problema=data.get('problema', ''),
        comentarios=data.get('comentarios', ''),
    )
    return JsonResponse({'id': anotacion.id, 'ok': True})


@staff_member_required
def api_eliminar_anotacion(request, anotacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    anotacion = get_object_or_404(Anotacion, id=anotacion_id)
    anotacion.delete()
    return JsonResponse({'ok': True})


@staff_member_required
def api_agregar_problema(request, evaluacion_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    data = json.loads(request.body)

    problema = ProblemaIdentificado.objects.create(
        evaluacion=evaluacion,
        descripcion=data.get('descripcion', ''),
        severidad=data.get('severidad', ''),
        tipo=data.get('tipo', ''),
        comentarios=data.get('comentarios', ''),
    )
    return JsonResponse({'id': problema.id, 'ok': True})


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
    evaluacion.observaciones_generales = data.get('observaciones', '')
    evaluacion.save()
    return JsonResponse({'ok': True})
