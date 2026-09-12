from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from .forms import SubjectProfileForm
from .models import SubjectProfile, TaskInfo, ClickInfo, TasksDescription, TaskStatus, Approved_Testers, Test_Input
from django.http import JsonResponse, Http404
from django.core.files.storage import FileSystemStorage
from datetime import date
import hashlib
import os
import json
from django.core import serializers
from django.http import HttpResponse


# --- Funciones auxiliares para obtener datos bajo demanda ---
def get_total_tasks():
    return TasksDescription.objects.all().count()

def get_total_active():
    return SubjectProfile.objects.all().count()

def get_task_answers(task_id):
    answer = TasksDescription.objects.get(task_id=task_id).answer
    return answer.split("|")

def validate_payid(payid):
    return SubjectProfile.objects.filter(payment_id=payid).count()

def json_serializer(input_data):
    json_obj = serializers.serialize('json', input_data)
    return json.loads(json_obj)

# --- Vistas ---
def user_registration(request):
    if 'payid' in request.session:
        if not validate_payid(request.session['payid']):
            form = SubjectProfileForm()
            return render(request, "main_templates/user_registration.html", {'form': form})
        else:
            return redirect('task_page')
    else:
        raise PermissionDenied

def main_page(request, task_id):
    if 'payid' in request.session and validate_payid(request.session['payid']):
        task = TasksDescription.objects.get(task_id=task_id)
        info = {
            'task': task,
            'task_count': get_total_tasks(),
            'options': task.valid_ans_options
        }
        return render(request, 'main_templates/recordmedia.html', info)
    else:
        raise PermissionDenied

def tasks_info_page(request):
    # Verificar que la sesión tenga payid
    payid = request.session.get('payid')
    if not payid:
        raise Http404("Please register first to take the test")

    # Verificar si el perfil ya existe
    profile_exists = SubjectProfile.objects.filter(payment_id=payid).exists()
    
    # Crear registro de TaskStatus si no existe
    task_status_exists = TaskStatus.objects.filter(subject_id=payid).exists()
    if not task_status_exists:
        TaskStatus.objects.create(subject_id=payid)

    # Si el perfil ya existe, ir a microtasks
    if profile_exists:
        return render(request, 'main_templates/microtasks.html', {})

    # Si el perfil no existe, procesar formulario
    if request.method == 'POST':
        form = SubjectProfileForm(request.POST or None)
        if form.is_valid():
            # Guardar sin commit para agregar campos de sesión
            profile = form.save(commit=False)
            profile.workerId = request.session.get('workerId', '0')
            profile.campId = request.session.get('campId', '0')
            profile.groupId = request.session.get('groupId', '0')
            profile.payment_id = payid
            profile.save()
            # Redirigir a microtasks después del registro exitoso
            return render(request, 'main_templates/microtasks.html', {})
        else:
            # Si el formulario no es válido, mostrar errores
            return render(request, 'main_templates/user_registration.html', {'form': form})
    else:
        # GET: mostrar formulario vacío
        form = SubjectProfileForm()
        return render(request, 'main_templates/user_registration.html', {'form': form})

def update_task_answers(request):
    if request.method != 'POST':
        return JsonResponse({'failure': 'Invalid method'}, status=400)
    
    data = request.POST.dict()
    ans = data.get("taskq")
    taskid = data.get("taskid")
    testid = request.session.get('payid')
    if not testid:
        return JsonResponse({'failure': 'Session expired'}, status=403)
    
    taskinfo, created = TaskInfo.objects.get_or_create(test_id=testid, task_id=taskid)
    if created:
        TaskInfo.objects.filter(test_id=testid, task_id=taskid).update(task_ans=ans)
    else:
        obj = TaskInfo.objects.filter(test_id=testid, task_id=taskid)
        json_obj = json_serializer(obj)
        current_answer = json_obj[0]['fields']['task_ans']
        new_answer = current_answer + ',' + ans
        TaskInfo.objects.filter(test_id=testid, task_id=taskid).update(task_ans=new_answer)
    return JsonResponse({'success': 'User response stored successfully'})

def update_clicks(request):
    if request.method != 'POST':
        return JsonResponse({'failure': 'Invalid method'}, status=400)
    
    data = request.POST.dict()
    click_info = data.get("clickinfo")
    taskid = data.get("taskid")
    testid = request.session.get('payid')
    if not testid:
        return JsonResponse({'failure': 'Session expired'}, status=403)
    
    clickinfo, created = ClickInfo.objects.get_or_create(test_id=testid, task_id=taskid)
    if created:
        ClickInfo.objects.filter(test_id=testid, task_id=taskid).update(click_info=click_info)
    else:
        obj = ClickInfo.objects.filter(test_id=testid, task_id=taskid)
        json_obj = json_serializer(obj)
        current_info = json_obj[0]['fields']['click_info']
        new_info = current_info + ',' + click_info
        ClickInfo.objects.filter(test_id=testid, task_id=taskid).update(click_info=new_info)
    return JsonResponse({'success': 'Click info stored successfully'})

def ins_page(request):
    # Valores por defecto fijos cuando no vienen en la URL
    DEFAULT_WORKER = 'DEMO2'
    DEFAULT_CAMP = 'demo'
    DEFAULT_GROUP = '1'

    # Obtener parámetros de la URL
    worker_id = request.GET.get('workerId')
    camp_id = request.GET.get('campId')
    group_id = request.GET.get('groupId')

    # Si falta alguno, redirigir con los valores por defecto fijos
    if not (worker_id and camp_id and group_id):
        return redirect(
            f'/index/?groupId={DEFAULT_GROUP}&campId={DEFAULT_CAMP}&workerId={DEFAULT_WORKER}'
        )

    # Guardar en sesión
    request.session['workerId'] = worker_id
    request.session['campId'] = camp_id
    request.session['groupId'] = group_id

    # Generar payment_id
    secret_key = "#####SHOULD_BE_REPLACED#####"
    payId = hashlib.sha256((camp_id + worker_id + secret_key).encode('utf-8')).hexdigest()
    payId = "mw-" + payId
    request.session['payid'] = payId

    # Renderizar página de instrucciones
    context = {
        'workerId': worker_id,
        'campId': camp_id,
        'groupId': group_id,
        'payId': payId
    }
    return render(request, 'main_templates/instructions.html', context)

def payment_id(request):
    if request.session.get('payid'):
        payid = request.session['payid']
        exists = validate_payid(payid)
        if exists > 0:
            # Obtener workerId del perfil
            profile = SubjectProfile.objects.get(payment_id=payid)
            worker_id = profile.workerId
            if worker_id:
                approval_table = Approved_Testers.objects.filter(workerId=worker_id).count()
                if not approval_table > 0:
                    Approved_Testers.objects.create(workerId=worker_id, status="pending")
        if exists > 0:
            res1 = TaskStatus.objects.get(subject_id=payid)
            # ... (cálculo de test_result y test_rating igual)
            # Usar get_total_tasks()
            total_tasks = get_total_tasks()
            return render(request, 'main_templates/payment.html', {'payId': payid, 'tasks': total_tasks})
    else:
        raise PermissionDenied

def upload_media(request):
    if request.method != 'POST':
        return JsonResponse({'failure': 'Invalid method'}, status=400)
    
    if 'file' not in request.FILES:
        return JsonResponse({'failure': 'No file uploaded'}, status=400)
    
    myfile = request.FILES['file']
    data = request.POST.dict()
    taskid = data.get("taskid")
    payId = request.session.get('payid')
    if not payId:
        return JsonResponse({'failure': 'Session expired'}, status=403)
    
    # Adaptar ruta para Windows (o usar una carpeta local)
    base_upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    folder = os.path.join(base_upload_dir, payId, taskid, str(date.today()))
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    fs = FileSystemStorage(location=folder)
    filename = f'_{payId}.webm'
    filename = fs.save(filename, myfile)
    return JsonResponse({'success': 'Media uploaded successfully'})

def Update_Test_Status(request):
    if request.method == 'POST':
        payId = request.session['payid']
        data = request.POST.dict()
        taskId = data.get("taskid")
        task_answer = data.get("taskq")
        silence = data.get("silence")
        task_time = data.get("task_time")
        task_time = int(task_time)
        silence = float(silence)

        # Calcular task_score
        if silence > 0 and silence <= 60 and task_time > 30:
            task_score = 5 if silence > 40 else 10
        else:
            task_score = 0

        # Obtener respuestas esperadas
        valid_answers = get_task_answers(taskId)

        if taskId == "1":
            task_status = "True" if task_answer in valid_answers else "False"
            TaskStatus.objects.filter(subject_id=payId).update(
                task_1_valid_question=task_status,
                task_1_time=task_time,
                task_1_score=task_score
            )
        elif taskId == "2":
            task_status = "True" if task_answer in valid_answers else "False"
            TaskStatus.objects.filter(subject_id=payId).update(
                task_2_valid_question=task_status,
                task_2_time=task_time,
                task_2_score=task_score
            )

        return JsonResponse({'success': 'status updated'})
    else:
        return JsonResponse({'failure': 'error during updating'})