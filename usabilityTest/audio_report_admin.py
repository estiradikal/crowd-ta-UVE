"""Consulta administrativa de informes ya sincronizados por el monitor de audio."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from .audio_report_views import _pdf_response
from .models import AudioMonitoringSession

@admin.register(AudioMonitoringSession)
class AudioMonitoringSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'participante', 'tarea', 'created_at',
                    'duration_seconds', 'speech_seconds', 'finalized', 'descargar_pdf')
    list_filter = ('finalized', 'task_id', 'created_at')
    search_fields = ('subject_id', 'task_id', 'session_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 50
    actions = None
    readonly_fields = tuple(field.name for field in AudioMonitoringSession._meta.fields) + ('descargar_pdf',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Participante')
    def participante(self, obj):
        return obj.subject_id

    @admin.display(description='Tarea')
    def tarea(self, obj):
        return obj.task_id

    @admin.display(description='Informe PDF')
    def descargar_pdf(self, obj):
        if not obj or not obj.finalized:
            return 'En curso: disponible al finalizar y sincronizar.'
        url = reverse('admin:usabilityTest_audiomonitoringsession_pdf', args=[obj.pk])
        return format_html('<a href="{}">Descargar PDF</a>', url)

    def get_urls(self):
        return [path('<uuid:session_id>/informe.pdf',
                     self.admin_site.admin_view(self.download_pdf),
                     name='usabilityTest_audiomonitoringsession_pdf')] + super().get_urls()

    def download_pdf(self, request, session_id):
        if request.method != 'GET':
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(['GET'])
        record = get_object_or_404(self.get_queryset(request), pk=session_id)
        if not self.has_view_permission(request, record):
            raise PermissionDenied
        if not record.finalized:
            return HttpResponse('El análisis aún no ha finalizado.', status=409,
                                content_type='text/plain; charset=utf-8')
        return _pdf_response([record], 'Informe de audio de la sesión',
                             f'crowdta-audio-{record.session_id}.pdf')
