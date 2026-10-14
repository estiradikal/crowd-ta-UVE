from django.db import migrations, models
import django.db.models.deletion


def migrate_descripciones(apps, schema_editor):
    ProblemaIdentificado = apps.get_model('usabilityTest', 'ProblemaIdentificado')
    CatalogoProblema = apps.get_model('usabilityTest', 'CatalogoProblema')

    mapping = {}
    counter = 1

    for row in ProblemaIdentificado.objects.all().order_by('id'):
        desc = (row.descripcion or '').strip() or '(Sin descripcion)'
        if desc not in mapping:
            codigo = f'PROB-{counter:03d}'
            while CatalogoProblema.objects.filter(codigo=codigo).exists():
                counter += 1
                codigo = f'PROB-{counter:03d}'
            cat = CatalogoProblema.objects.create(codigo=codigo, descripcion=desc)
            mapping[desc] = cat.pk
            counter += 1
        if row.problema_id is None:
            row.problema_id = mapping[desc]
            row.save(update_fields=['problema_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('usabilityTest', '0007_evaluacion_fecha_fin_evaluacion_fecha_inicio_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CatalogoProblema',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(default='', editable=False, max_length=16, unique=True)),
                ('descripcion', models.TextField()),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Problema de Catalogo',
                'verbose_name_plural': 'Problemas de Catalogo',
            },
        ),
        migrations.AddField(
            model_name='problemaidentificado',
            name='problema',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ocurrencias', to='usabilityTest.catalogoproblema'),
        ),
        migrations.RunPython(migrate_descripciones, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='problemaidentificado',
            name='problema',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ocurrencias', to='usabilityTest.catalogoproblema'),
        ),
        migrations.RemoveField(
            model_name='problemaidentificado',
            name='descripcion',
        ),
    ]
