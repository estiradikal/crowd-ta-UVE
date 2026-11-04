"""Descarga del informe de audio de la propia sesión del participante."""
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from .audio_report import build_audio_report
from .models import AudioMonitoringSession

def _pdf_response(records, title, filename):
    try:
        content = build_audio_report(records, title=title)
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith('reportlab'):
            return HttpResponse('El generador PDF no está instalado. Instale requirements-audio.txt.', status=503, content_type='text/plain; charset=utf-8')
        raise
    response = HttpResponse(content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response

@require_GET
def download_own_audio_report(request, session_id):
    subject_id = request.session.get('payid')
    if not subject_id:
        raise PermissionDenied
    try:
        record = AudioMonitoringSession.objects.get(session_id=session_id, subject_id=subject_id)
    except AudioMonitoringSession.DoesNotExist:
        raise Http404('No se encontró el registro de audio de esta sesión.')
    if not record.finalized:
        return HttpResponse('El análisis aún no ha finalizado.', status=409, content_type='text/plain; charset=utf-8')
    return _pdf_response([record], 'Informe de audio de la sesión', f'crowdta-audio-{record.session_id}.pdf')
