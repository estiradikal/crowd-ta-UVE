from django.db import models
from django_countries.fields import CountryField
#from languages.fields import LanguageField
#from gsheets import mixins    --> Ya no se usará


class MarkdownModel(models.Model):
    markdown = models.TextField(null=True, blank=True, default="")
    MARKDOWN_FIELDS = ()

    class Meta:
        abstract = True

    def to_markdown(self):
        lines = ["| Campo | Valor |", "| --- | --- |"]
        for name in self.MARKDOWN_FIELDS:
            lines.append("| %s | %s |" % (name, md_value(getattr(self, name))))
        return "\n".join(lines)

    def save(self, *args, **kwargs):
        self.markdown = self.to_markdown()
        super().save(*args, **kwargs)


def md_value(value):
    if value is None:
        return ""
    if hasattr(value, "code") and hasattr(value, "name"):
        value = value.code
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


class SubjectProfile(MarkdownModel):
    age = models.IntegerField()
    gender = models.CharField(max_length=32)
    birth_country = CountryField(null=False)
    residence_country = CountryField(null=False)
    mother_tongue = models.CharField(max_length=32, null=False, default="unknown")
    Do_you_speak_English = models.CharField(max_length=32, null=False, default="none")
    participated_before = models.CharField(max_length=32, null=False)
    knowledge_on_usability = models.CharField(max_length=32, null=False)
    payment_id = models.CharField(max_length=128, default="Id not saved", primary_key=True)
    
    # Campos renombrados y nuevo
    workerId = models.CharField(max_length=32, null=False, default="0")
    campId = models.CharField(max_length=32, null=False, default="0")
    groupId = models.CharField(max_length=32, null=True, blank=True)
    test_status = models.CharField(max_length=32, default="active")
    campId = models.CharField(max_length=32, null=True, blank=True)

    MARKDOWN_FIELDS = (
        "payment_id", "age", "gender", "birth_country", "residence_country",
        "mother_tongue", "Do_you_speak_English", "knowledge_on_usability",
        "participated_before", "test_status", "workerId", "campId", "groupId",
    )

    def __str__(self):
        return self.payment_id


class TaskInfo(MarkdownModel):
    id = models.AutoField(primary_key=True)
    task_id = models.CharField(max_length=64, null=True, default="id not saved")
    task_ans = models.CharField(max_length=1024, null=True)
    test_id = models.CharField(max_length=128, null=False, default="Id not saved")

    MARKDOWN_FIELDS = ("id", "task_id", "task_ans", "test_id")


class ClickInfo(MarkdownModel):
    id = models.AutoField(primary_key=True)
    test_id = models.CharField(max_length=128, null=False, default="Id not saved")
    task_id = models.CharField(max_length=32, null=True, default="id not saved")
    click_info = models.TextField(null=True)

    MARKDOWN_FIELDS = ("id", "test_id", "task_id", "click_info")


class TasksDescription(MarkdownModel):
    task_id = models.CharField(max_length=16, primary_key=True)
    task_description = models.TextField(null=True, default="Task description here")
    task_valid_question = models.TextField(null=True, default="Task validation question here")
    valid_ans_options = models.CharField(max_length=128, default="[]")
    answer = models.CharField(max_length=128, null=True)

    MARKDOWN_FIELDS = (
        "task_id", "task_description", "task_valid_question",
        "valid_ans_options", "answer",
    )

    def __str__(self):
        return self.task_id


class TaskStatus(MarkdownModel):
    subject_id = models.CharField(max_length=128, primary_key=True, default="id not saved")
    task_1_valid_question = models.CharField(max_length=32, null=True)
    task_1_score = models.IntegerField(null=True, blank=True)
    task_1_time = models.IntegerField(null=True, blank=True, default=0)
    task_2_valid_question = models.CharField(max_length=32, null=True)
    task_2_score = models.IntegerField(null=True, blank=True)
    task_2_time = models.IntegerField(null=True, blank=True, default=0)
    test_result = models.CharField(max_length=32, null=True)
    test_rating = models.CharField(max_length=32, null=True)

    MARKDOWN_FIELDS = (
        "subject_id", "task_1_valid_question", "task_1_score", "task_1_time",
        "task_2_valid_question", "task_2_score", "task_2_time",
        "test_result", "test_rating",
    )

    def __str__(self):
        return self.subject_id


class Test_Input(MarkdownModel):
    campId = models.CharField(max_length=64, primary_key=True, default="0")
    secret_key = models.CharField(max_length=100, null=True, default="secret-key")
    application_url = models.CharField(max_length=100, null=True, default="url")

    MARKDOWN_FIELDS = ("campId", "secret_key", "application_url")

    def __str__(self):
        return self.campId


class Approved_Testers(MarkdownModel):
    workerId = models.CharField(max_length=128, null=False, primary_key=True, default="0")
    status = models.CharField(max_length=32, null=True)

    MARKDOWN_FIELDS = ("workerId", "status")

    def __str__(self):
        return self.workerId


class InstructionsPage(models.Model):
    """Contenido textual de la plataforma guardado como Markdown en la BD.

    Se renderiza en el navegador con marked.js (ver templates).
    """

    key = models.CharField(max_length=64, primary_key=True, default="general_instructions")
    title = models.CharField(max_length=128, default="Instructions")
    content_md = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Instructions page"
        verbose_name_plural = "Instructions pages"

    def __str__(self):
        return self.key