from django.urls import path, re_path
from . import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("registration/", views.user_registration, name="user_registration"),
   # re_path(r'^products/$', views.login_page, name="login_page"),
    path('payId/', views.payment_id, name="payment_id"),
    re_path('index/$', views.ins_page, name="ins_page"),
    path('test/<int:task_id>', views.main_page, name="test_page"),
    path('tasks/', views.tasks_info_page, name="task_page"),
    path('validate/', views.update_task_answers, name="tap"),
    path('upload/', views.upload_media, name="upload_media"),
    path('clickinfo/', views.update_clicks, name="upload_clicks"),
    path('statusupdate/', views.Update_Test_Status, name="update_status"),
   ]