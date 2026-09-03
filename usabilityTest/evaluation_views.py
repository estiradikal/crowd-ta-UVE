import os
from django.shortcuts import render, get_object_or_404
from django.http import FileResponse, Http404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q

from .models import Evaluacion


def get_uploaded_videos():
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    videos = []
    if not os.path.exists(base_dir):
        return videos

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
        videos = [v for v in videos if busqueda.lower() in v['payment_id'].lower()]

    total_videos = len(get_uploaded_videos())
    total_evaluados = Evaluacion.objects.filter(completada=True).count()
    total_pendientes = total_videos - total_evaluados

    context = {
        'videos': videos,
        'filtro': filtro,
        'busqueda': busqueda,
        'stats': {
            'total': total_videos,
            'evaluados': total_evaluados,
            'pendientes': total_pendientes,
        }
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
                            'url': f'/evaluacion/video/{payment_id}/{task_id}/{date_folder}/{f}',
                        })

    if not video_files:
        raise Http404("No se encontraron videos para este worker/task")

    evaluacion, created = Evaluacion.objects.get_or_create(
        payment_id=payment_id,
        task_id=task_id,
        defaults={
            'video_id': video_files[0]['filename'],
        }
    )

    context = {
        'evaluacion': evaluacion,
        'payment_id': payment_id,
        'task_id': task_id,
        'video_files': video_files,
    }
    return render(request, 'evaluation/evaluar_video.html', context)


@staff_member_required
def serve_video(request, payment_id, task_id, date_folder, filename):
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    filepath = os.path.join(base_dir, payment_id, task_id, date_folder, filename)

    if not os.path.exists(filepath):
        raise Http404("Video no encontrado")

    response = FileResponse(open(filepath, 'rb'), content_type='video/webm')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
