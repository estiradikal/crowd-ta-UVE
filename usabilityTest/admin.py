from django.contrib import admin
from .models import SubjectProfile, TaskInfo, ClickInfo, TasksDescription, TaskStatus, Approved_Testers, Evaluacion
# Register your models here.
admin.site.register(SubjectProfile)
admin.site.register(TaskInfo)
admin.site.register(ClickInfo)
admin.site.register(TasksDescription)
admin.site.register(TaskStatus)
admin.site.register(Approved_Testers)
admin.site.register(Evaluacion)
