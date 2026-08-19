from django.db import models
from django_countries.fields import CountryField
from languages.fields import LanguageField
from gsheets import mixins
# Create your models here.


class SubjectProfile(models.Model):
 
    age         = models.IntegerField()
    gender      = models.CharField(max_length=32)
    birth_country     = CountryField(null=False)
    residence_country = CountryField(null=False)
    mother_tongue = LanguageField(max_length=32, null=False)
    Do_you_speak_English = models.CharField(max_length=32, null=False, default = "none")
    participated_before = models.CharField(max_length=32, null=False)
    knowledge_on_usability = models.CharField(max_length=32, null=False)
    payment_id = models.CharField(max_length=128,default = "Id not saved", primary_key=True)
    mw_id = models.CharField(max_length=32, null=False, default = "mw-id")
    test_status = models.CharField(max_length=32, default = "active")
    

class TaskInfo(models.Model):

    id = models.AutoField(primary_key=True)
    task_id = models.CharField(max_length=64, null=True, default = "id not saved")
    task_ans = models.CharField(max_length=1024,null=True)
    test_id = models.CharField(max_length=128, null=False,default = "Id not saved")

class ClickInfo(models.Model):

    id = models.AutoField(primary_key=True)
    test_id = models.CharField(max_length=128, null=False,default = "Id not saved")
    task_id = models.CharField(max_length=32, null=True, default = "id not saved")
    click_info = models.TextField(null=True)

class TasksDescription(models.Model):

    task_id = models.CharField(max_length=16, primary_key=True)
    task_description = models.TextField(null=True, default="Task description here")
    task_valid_question = models.TextField(null=True, default="Task validation question here")
    valid_ans_options = models.CharField(max_length=128, default="[]")
    answer = models.CharField(max_length=128, null=True)


class TaskStatus(mixins.SheetPushableMixin, models.Model):

    spreadsheet_id = '1ALs2HgtPdT-k0JHq5dzqMcBp5v38j8sj0v_E6lJJ0Ws'
    model_id_field = 'subject_id'
    
    subject_id = models.CharField(max_length=128, primary_key=True, default = "id not saved")
    task_1_valid_question = models.CharField(max_length=32, null=True)
    task_1_score = models.IntegerField(null=True, blank=True)
    task_1_time =  models.IntegerField(null=True, blank=True, default=0)
    task_2_valid_question = models.CharField(max_length=32, null=True)
    task_2_score = models.IntegerField(null=True,blank=True)
    task_2_time =  models.IntegerField(null=True, blank=True, default=0)
    test_result = models.CharField(max_length=32, null=True)
    test_rating = models.CharField(max_length=32, null=True)

class Test_Input(models.Model):
    campaign_id = models.CharField(max_length=64, primary_key=True, default = "Campaign-Id")
    secret_key = models.CharField(max_length=100,  null=True, default = "secret-key")
    application_url = models.CharField(max_length=100,  null=True, default = "url")

class Approved_Testers(mixins.SheetSyncableMixin,models.Model):
    spreadsheet_id = '1ALs2HgtPdT-k0JHq5dzqMcBp5v38j8sj0v_E6lJJ0Ws'
    sheet_name = 'Sheet2'
    model_id_field = 'mw_id'
    mw_id = models.CharField(max_length=128, null=False,primary_key=True, default = "mw-id")
    status = models.CharField(max_length=32, null=True)
    