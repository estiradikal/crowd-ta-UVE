from django.db import migrations

TRAINING_SESSION_MD = """### **Important**

1. To start the task, you should **allow permissions for Screen Share, Mic, and Camera** as shown below:

<img src="/static/img/permissions.jpg" alt="allow-permissions" class="instructions-img" style="max-width: 60%;">

The camera recording is optional, you can disable it later. Make sure to maximize your browser window for the screen recording and to not display any private information during the recording session.

2. **Follow the steps on the left panel** to complete the tasks:

<img src="/static/img/left_panel.JPG" alt="left panel" class="instructions-img" style="max-width: 60%;">

3. If you **do not speak** or remain silent, the following message will be displayed:

<img src="/static/img/notify.JPG" alt="notification" class="instructions-img" style="width: 9%; max-width: 170px;">
"""


def seed_training_session(apps, schema_editor):
    InstructionsPage = apps.get_model("usabilityTest", "InstructionsPage")
    InstructionsPage.objects.update_or_create(
        key="training_session",
        defaults={
            "title": "Part 2: Training session",
            "content_md": TRAINING_SESSION_MD,
        },
    )


def unseed_training_session(apps, schema_editor):
    InstructionsPage = apps.get_model("usabilityTest", "InstructionsPage")
    InstructionsPage.objects.filter(key="training_session").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usabilityTest", "0007_instructionspage"),
    ]

    operations = [
        migrations.RunPython(seed_training_session, unseed_training_session),
    ]
