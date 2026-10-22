from django.urls import path
from django.contrib.auth import views as auth_views
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
    path('admin-panel/campanas/nueva/', evaluation_views.crear_campana, name='admin_crear_campana'),
    path('admin-panel/reportes/', evaluation_views.reportes, name='admin_reportes'),
    path('admin-panel/tabla-anotaciones/', evaluation_views.tabla_anotaciones, name='admin_tabla_anotaciones'),
    path('admin-panel/guia/', evaluation_views.guia_evaluacion, name='admin_guia'),
    path('admin-panel/config/', evaluation_views.config_panel, name='admin_config'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/index/'), name='logout'),
    # API
    path('admin-panel/api/<int:evaluacion_id>/datos/', evaluation_views.api_cargar_datos, name='api_cargar_datos'),
    path('admin-panel/api/<int:evaluacion_id>/anotacion/', evaluation_views.api_agregar_anotacion, name='api_agregar_anotacion'),
    path('admin-panel/api/anotacion/<int:anotacion_id>/editar/', evaluation_views.api_editar_anotacion, name='api_editar_anotacion'),
    path('admin-panel/api/anotacion/<int:anotacion_id>/eliminar/', evaluation_views.api_eliminar_anotacion, name='api_eliminar_anotacion'),
    path('admin-panel/api/catalogo-problemas/', evaluation_views.api_catalogo_problemas, name='api_catalogo_problemas'),
    path('admin-panel/api/catalogo-problemas/crear/', evaluation_views.api_crear_problema, name='api_crear_problema'),
    path('admin-panel/api/<int:evaluacion_id>/problema/', evaluation_views.api_agregar_problema, name='api_agregar_problema'),
    path('admin-panel/api/problema/<int:problema_id>/editar/', evaluation_views.api_editar_problema, name='api_editar_problema'),
    path('admin-panel/api/problema/<int:problema_id>/eliminar/', evaluation_views.api_eliminar_problema, name='api_eliminar_problema'),
    path('admin-panel/api/<int:evaluacion_id>/tiempo/', evaluation_views.api_registrar_tiempo, name='api_registrar_tiempo'),
    path('admin-panel/api/<int:evaluacion_id>/completar/', evaluation_views.api_completar_evaluacion, name='api_completar_evaluacion'),
]
