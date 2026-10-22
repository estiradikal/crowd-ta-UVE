from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import PermissionDenied, RequestAborted
from .forms import SubjectProfileForm
from .models import SubjectProfile, TaskInfo, ClickInfo, TasksDescription, TaskStatus, Approved_Testers
from django.http import JsonResponse, Http404
from django.core.files.storage import FileSystemStorage
from datetime import date,datetime
import hashlib
import os
import json
from django.core import serializers
from django import template

Total_Tasks_= TasksDescription.objects.all().count()
Total_Active = SubjectProfile.objects.all().count()
Task_1_Answer = TasksDescription.objects.get(task_id=1).answer
Task_1_Answer = Task_1_Answer.split("|");
Task_2_Answer = TasksDescription.objects.get(task_id=2).answer
Task_2_Answer = Task_2_Answer.split("|");


def validate_payid(payid) :
    exists = SubjectProfile.objects.filter(payment_id=payid).count()
    return exists

def json_serialzer(input):
    jsonObj = serializers.serialize('json', input)
    output = json.loads(jsonObj)
    return output

def user_registration(request):
    if(request.session['payid']):
        exist = validate_payid(request.session['payid'])
        if  not exist  > 0:
            form = SubjectProfileForm()
            return render(request, "main_templates/user_registration.html", {'form': form})
        else :
            return redirect('task_page')
    else :
        raise PermissionDenied
     
    
def main_page(request, task_id):
    if(request.session['payid']):
        exist = validate_payid(request.session['payid']) 
        if exist  > 0:
            task = TasksDescription.objects.get(task_id=task_id)
            options = task.valid_ans_options
            info = {
                'task':task,
                'task_count':Total_Tasks_,
                'options': options
            }
            return render(request, 'main_templates/recordmedia.html', info)
        else:
            raise Http404("you have not registered for the test")
    else :
        raise PermissionDenied

def tasks_info_page(request):
    if(request.session['payid']):
        payid = request.session['payid']
        print(payid)
        exists = SubjectProfile.objects.filter(payment_id=payid).count()
        test_status = TaskStatus.objects.filter(subject_id=payid).count()
        if not test_status > 0:
            TaskStatus.objects.create(subject_id=payid)       
        if not exists > 0:
            if request.method == 'POST':     
                form = SubjectProfileForm(request.POST or None)      
                if form.is_valid():
                    form_up = form.save(commit=False)
                    payId = request.session['payid']
                    mwId = request.session['mwid'] 
                    form_up.payment_id = payId
                    form_up.mw_id = mwId
                    form_up.save()
        return render(request, 'main_templates/microtasks.html', {})       
    else: 
        raise Http404("Please register first to take the test")

def update_task_answers(request):
    if request.method == 'POST':
        data = request.POST.dict()
        ans = data.get("taskq")
        taskid =  data.get("taskid") 
        testid = request.session['payid']
        taskinfo, created = TaskInfo.objects.filter(test_id=testid).get_or_create(task_id=taskid,test_id=testid)
        if created:
            TaskInfo.objects.filter(test_id=testid).filter(task_id=taskid).update(task_ans=ans)      
        else:
            obj = TaskInfo.objects.filter(test_id=testid,task_id=taskid)
            jsonObj = json_serialzer(obj)
            currentAnswer = jsonObj[0]['fields']['task_ans']
            currentAnswer = currentAnswer+','+ans
            TaskInfo.objects.filter(test_id=testid).filter(task_id=taskid).update(task_ans=currentAnswer)
        return JsonResponse({'success': 'User response stored successfully'})
    else:
        return JsonResponse({'failure': 'response not saved'})

def update_clicks(request):
    if request.method == 'POST':
        data = request.POST.dict()
        click_info = data.get("clickinfo")
        taskid =  data.get("taskid") 
        testid = request.session['payid']
        clickinfo, created = ClickInfo.objects.filter(test_id=testid).get_or_create(task_id=taskid,test_id=testid)
        if created:
            ClickInfo.objects.filter(test_id=testid).filter(task_id=taskid).update(click_info=click_info)      
        else:
            obj = ClickInfo.objects.filter(test_id=testid,task_id=taskid)
            jsonObj = json_serialzer(obj)
            currentinfo = jsonObj[0]['fields']['click_info']
            currentinfo = currentinfo+','+click_info
            ClickInfo.objects.filter(test_id=testid).filter(task_id=taskid).update(click_info=currentinfo)
        return JsonResponse({'success': 'User response stored successfully'})
    else:
        return JsonResponse({'failure': 'response not saved'})

def ins_page(request):
    Total_Active = SubjectProfile.objects.all().count()
    Total_accepted = Approved_Testers.objects.filter(status="approved").count()
    print(Total_accepted);
    if Total_accepted <= 30:
        if Total_Active <= 201:     
            if request.method == 'GET':
                if 'payid' in request.session:
                    del request.session['payid']
                if 'mwid' in request.session:
                    del request.session['mwid']

                worker_id = request.GET['workerId']
                camp_id = request.GET['campId']
                secret_key = "#####SHOULD_BE_REPLACED#####"
                payId = hashlib.sha256(str(camp_id+worker_id+secret_key).encode('utf-8')).hexdigest()
                payId = "mw-"+payId
            
                exists = validate_payid(payId) 
                request.session['mwid'] = worker_id
                request.session['payid'] = payId

                if not exists > 0:
                    return render(request, 'main_templates/instructions.html', {})
                else :
                    return redirect('task_page')
        else:
            return render(request, 'main_templates/serverbusy.html')
    else:
        return render(request, 'main_templates/campaign_success')

def payment_id(request):
    if(request.session['payid']):
        payid = request.session['payid']
        exists = validate_payid(payid)
        if exists > 0:
            approval_table = Approved_Testers.objects.filter(mw_id=payid).count()
            if not approval_table > 0:
                new_approval_row = Approved_Testers.objects.create(mw_id=payid)
        if exists > 0:
            res1 = TaskStatus.objects.get(subject_id=payid)
            test_result = ""
            test_rating = ""
            if res1.task_1_valid_question == "True" or res1.task_2_valid_question == "True":
                if res1.task_1_score*1 + res1.task_2_score*1 >= 10:
                    test_result = "valid result"
                    test_rating = "good"
                if res1.task_1_score*1 + res1.task_2_score*1 < 10:
                    test_result = "invalid result"
                    test_rating = "bad"
            if res1.task_1_valid_question == "True" and res1.task_2_valid_question == "True":
                if res1.task_1_score*1 + res1.task_2_score*1 >= 15:
                    test_result = "valid result"
                    test_rating = "excellent"
                if res1.task_1_score*1 + res1.task_2_score*1 < 15 and res1.task_1_score*1 + res1.task_2_score*1 >= 10:
                    test_result = "valid result"
                    test_rating = "good"
                if res1.task_1_score*1 + res1.task_2_score*1 < 10:
                    test_result = "invalid result"
                    test_rating = "bad"
            TaskStatus.objects.filter(subject_id=payid).update(test_result=test_result, test_rating=test_rating)
            SubjectProfile.objects.filter(payment_id=payid).update(test_status="Completed")
            return render(request, 'main_templates/payment.html', {'payId':payid,'tasks':Total_Tasks_})
    else:
        raise PermissionDenied

def upload_media(request):
    if request.method == 'POST':
        myfile = request.FILES['file']
        data = request.POST.dict()
        print(data)
        taskid =  data.get("taskid")
        print(taskid)
        payId = request.session['payid']
        folder = '/home/rgalda/ta_crowdsource/uploads/'+payId+'/'+taskid+'/'+str(date.today())
        fs = FileSystemStorage(location=folder)
        filename = '_'+payId +'_'+'.webm' 
        filename = fs.save(filename, myfile)
        file_url = fs.url(filename)
        return JsonResponse({'success': 'Media uploaded Successfully'})

    else:

        return JsonResponse({'failure': 'Media not saved'})

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
        
        if silence > 0 and silence <= 60 and task_time > 30:
            if silence > 40:
                task_score = 5
            if silence <= 40:
                task_score = 10
        else :
            task_score = 0

        if taskId == "1":
            if task_answer in Task_1_Answer:
                task_status = "True"
            else :
                task_status = "False"
            TaskStatus.objects.filter(subject_id=payId).update(task_1_valid_question=task_status,task_1_time=task_time, task_1_score=task_score)
        if taskId == "2":
            if task_answer in Task_2_Answer:
                task_status = "True"
            else :
                task_status = "False"
            TaskStatus.objects.filter(subject_id=payId).update(task_2_valid_question=task_status,task_2_time=task_time,task_2_score=task_score)
        
        return JsonResponse({'success': 'status updated'})
    else:
        return JsonResponse({'failure': 'error during updating'})
    




     