from django.urls import path
from . import evaluation_views

urlpatterns = [
    # Admin Panel
    path('admin-panel/', evaluation_views.dashboard, name='admin_dashboard'),
    path('admin-panel/videos/', evaluation_views.lista_videos, name='admin_lista_videos'),
    path('admin-panel/video/<str:payment_id>/<str:task_id>/<str:date_folder>/<str:filename>/',
         evaluation_views.serve_video, name='serve_video'),
    path('admin-panel/evaluar/<str:payment_id>/<str:task_id>/',
         evaluation_views.evaluar_video, name='admin_evaluar_video'),
    path('admin-panel/campanas/', evaluation_views.campanas, name='admin_campanas'),
    path('admin-panel/reportes/', evaluation_views.reportes, name='admin_reportes'),
    path('admin-panel/guia/', evaluation_views.guia_evaluacion, name='admin_guia'),
    path('admin-panel/config/', evaluation_views.config_panel, name='admin_config'),
    # API
    path('admin-panel/api/<int:evaluacion_id>/datos/', evaluation_views.api_cargar_datos, name='api_cargar_datos'),
    path('admin-panel/api/<int:evaluacion_id>/anotacion/', evaluation_views.api_agregar_anotacion, name='api_agregar_anotacion'),
    path('admin-panel/api/anotacion/<int:anotacion_id>/eliminar/', evaluation_views.api_eliminar_anotacion, name='api_eliminar_anotacion'),
    path('admin-panel/api/<int:evaluacion_id>/problema/', evaluation_views.api_agregar_problema, name='api_agregar_problema'),
    path('admin-panel/api/problema/<int:problema_id>/eliminar/', evaluation_views.api_eliminar_problema, name='api_eliminar_problema'),
    path('admin-panel/api/<int:evaluacion_id>/completar/', evaluation_views.api_completar_evaluacion, name='api_completar_evaluacion'),
]
