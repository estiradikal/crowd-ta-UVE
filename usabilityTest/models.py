from django.db import models
from django_countries.fields import CountryField
#from languages.fields import LanguageField
#from gsheets import mixins    --> Ya no se usará

class SubjectProfile(models.Model):
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

    def __str__(self):
        return self.payment_id


class TaskInfo(models.Model):
    id = models.AutoField(primary_key=True)
    task_id = models.CharField(max_length=64, null=True, default="id not saved")
    task_ans = models.CharField(max_length=1024, null=True)
    test_id = models.CharField(max_length=128, null=False, default="Id not saved")


class ClickInfo(models.Model):
    id = models.AutoField(primary_key=True)
    test_id = models.CharField(max_length=128, null=False, default="Id not saved")
    task_id = models.CharField(max_length=32, null=True, default="id not saved")
    click_info = models.TextField(null=True)


class TasksDescription(models.Model):
    task_id = models.CharField(max_length=16, primary_key=True)
    task_description = models.TextField(null=True, default="Task description here")
    task_valid_question = models.TextField(null=True, default="Task validation question here")
    valid_ans_options = models.CharField(max_length=128, default="[]")
    answer = models.CharField(max_length=128, null=True)


class TaskStatus(models.Model):
    subject_id = models.CharField(max_length=128, primary_key=True, default="id not saved")
    task_1_valid_question = models.CharField(max_length=32, null=True)
    task_1_score = models.IntegerField(null=True, blank=True)
    task_1_time = models.IntegerField(null=True, blank=True, default=0)
    task_2_valid_question = models.CharField(max_length=32, null=True)
    task_2_score = models.IntegerField(null=True, blank=True)
    task_2_time = models.IntegerField(null=True, blank=True, default=0)
    test_result = models.CharField(max_length=32, null=True)
    test_rating = models.CharField(max_length=32, null=True)


class Test_Input(models.Model):
    campId = models.CharField(max_length=64, primary_key=True, default="0")
    secret_key = models.CharField(max_length=100, null=True, default="secret-key")
    application_url = models.CharField(max_length=100, null=True, default="url")


class Approved_Testers(models.Model):
    workerId = models.CharField(max_length=128, null=False, primary_key=True, default="0")
    status = models.CharField(max_length=32, null=True)


class Evaluacion(models.Model):
    video_id = models.CharField(max_length=256)
    payment_id = models.CharField(max_length=256)
    task_id = models.CharField(max_length=32)
    completada = models.BooleanField(default=False)
    evaluador = models.CharField(max_length=128, null=True, blank=True, default="")
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    observaciones_generales = models.TextField(blank=True, default="")
    # Tiempo real anotando (solo cuenta mientras la pagina de evaluacion esta visible)
    tiempo_activo_segundos = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Evaluacion"
        verbose_name_plural = "Evaluaciones"

    @property
    def duracion_segundos(self):
        """Hoja '3. Time annotation': annotation_finish_time - annotation_start_time."""
        if not self.fecha_inicio or not self.fecha_fin:
            return None
        return max(0, int((self.fecha_fin - self.fecha_inicio).total_seconds()))

    @property
    def duracion_texto(self):
        return formato_hms(self.duracion_segundos)

    @property
    def tiempo_activo_texto(self):
        return formato_hms(self.tiempo_activo_segundos)

    def __str__(self):
        return f"{self.payment_id} - Task {self.task_id}"


def formato_hms(segundos):
    if segundos is None:
        return ''
    horas, resto = divmod(int(segundos), 3600)
    return f"{horas:02d}:{resto // 60:02d}:{resto % 60:02d}"


class Anotacion(models.Model):
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE, related_name='anotaciones')
    start_time = models.CharField(max_length=16)
    finish_time = models.CharField(max_length=16, blank=True, default="")
    indicador = models.CharField(max_length=16)
    contexto = models.CharField(max_length=64)
    # Texto del problema (se mantiene sincronizado con problema_ref para exportar / mostrar)
    problema = models.TextField(blank=True, default="")
    # Vinculo al catalogo: permite contar ocurrencias por problema y corregir el texto en un solo lugar
    problema_ref = models.ForeignKey('CatalogoProblema', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='anotaciones')
    comentarios = models.TextField(blank=True, default="")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Anotacion"
        verbose_name_plural = "Anotaciones"
        ordering = ['start_time', 'id']

    def save(self, *args, **kwargs):
        if self.problema_ref_id:
            self.problema = self.problema_ref.descripcion
        super().save(*args, **kwargs)

    def duracion_segundos(self):
        """Duracion de la anotacion en segundos, o None si no hay finish_time valido."""
        ini, fin = parse_mmss(self.start_time), parse_mmss(self.finish_time)
        if ini is None or fin is None or fin < ini:
            return None
        return fin - ini

    def __str__(self):
        return f"{self.indicador} ({self.start_time} - {self.finish_time})"


def parse_mmss(value):
    """Convierte 'MM:SS' a segundos. Devuelve None si el formato no es valido."""
    try:
        mins, secs = str(value).strip().split(':')
        mins, secs = int(mins), int(secs)
    except (ValueError, AttributeError):
        return None
    if mins < 0 or not 0 <= secs < 60:
        return None
    return mins * 60 + secs


class CatalogoProblema(models.Model):
    codigo = models.CharField(max_length=16, unique=True, editable=False, default="")
    descripcion = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Problema de Catalogo"
        verbose_name_plural = "Problemas de Catalogo"

    def save(self, *args, **kwargs):
        if not self.codigo:
            max_n = 0
            for code in CatalogoProblema.objects.values_list('codigo', flat=True):
                try:
                    max_n = max(max_n, int(str(code).split('-')[-1]))
                except (ValueError, TypeError):
                    continue
            self.codigo = f"PROB-{max_n + 1:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.descripcion[:50]}"


class ProblemaIdentificado(models.Model):
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE, related_name='problemas')
    problema = models.ForeignKey(CatalogoProblema, on_delete=models.CASCADE, related_name='ocurrencias')
    severidad = models.CharField(max_length=32)
    tipo = models.CharField(max_length=32)
    comentarios = models.TextField(blank=True, default="")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Problema Identificado"
        verbose_name_plural = "Problemas Identificados"

    def __str__(self):
        return f"{self.problema.codigo} - {self.severidad}"