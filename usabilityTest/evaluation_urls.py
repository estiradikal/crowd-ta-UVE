from django.urls import path
from . import evaluation_views

urlpatterns = [
    path('evaluacion/', evaluation_views.lista_videos, name='eval_lista_videos'),
    path('evaluacion/video/<str:payment_id>/<str:task_id>/<str:date_folder>/<str:filename>/',
         evaluation_views.serve_video, name='serve_video'),
    path('evaluacion/<str:payment_id>/<str:task_id>/',
         evaluation_views.evaluar_video, name='evaluar_video'),
]
