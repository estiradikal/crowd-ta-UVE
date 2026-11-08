from django.db import migrations


def backfill_campaigns(apps, schema_editor):
    """Registra como campaña cada campId que ya tienen los participantes."""
    SubjectProfile = apps.get_model('usabilityTest', 'SubjectProfile')
    Test_Input = apps.get_model('usabilityTest', 'Test_Input')
    camp_ids = SubjectProfile.objects.exclude(campId__isnull=True).exclude(campId='').values_list('campId', flat=True)
    for camp_id in set(camp_ids):
        Test_Input.objects.get_or_create(campId=camp_id[:64], defaults={'application_url': ''})


class Migration(migrations.Migration):

    dependencies = [
        ('usabilityTest', '0009_evaluatorprofile_shortcuts'),
    ]

    operations = [
        migrations.RunPython(backfill_campaigns, migrations.RunPython.noop),
    ]
