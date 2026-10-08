from django.db import migrations, models

DEFAULT_INSTRUCTIONS_MD = """# Instructions

This task is a **10 minute experiment** to test the **ease of use** of an application. It is **not an exam to test your capabilities**. So, perform tasks without worry about doing something wrong as **there is no wrong way** in the test.

The test has **three parts**:

## Part 1: Demographic Questionnaire

- Here you should **answer the questions providing valid information**.
- These data would help us understand the influence of your background on the perceived ease of use of an application.

## Part 2: Training session

You watch a **short demo video** for the next part.

## Part 3: Searching tasks

- **You must speak out** your feelings and mind throughout while testing an application.
- Your **browser, audio, and (optional) video are recorded** for our analysis.

**IMPORTANT:** You will be informed before the audio and video recording starts. If you feel uncomfortable sharing the screen, audio, and video recordings, please do not proceed with this task.

### Important

- You must **speak** your feelings and mind throughout the task.
- It is important that you **speak in English**.
- If you don't speak for a while, the following message appears:

![Keep talking notification](/static/img/notify.JPG)

## Payment information

After you finish all the tasks, you get a **Payment-id**. Save it and use it as reference for your payment. If you do not speak at all, you won't get paid.

## Feedback and help

If you feel inconvenience or face issues during the experiment, please write to us at [ta.crowdsource@gmail.com](mailto:ta.crowdsource@gmail.com) with your workerId in the subject.

## Use of Recorded Data

All recordings will be evaluated by a small group of researchers. The recording will not be shared otherwise, or published online. The video recording will be deleted after evaluation, at latest 31. December 2021. The screen recording will also be deleted after evaluation, at latest 31. December 2021, if they contain any personal information. The audio recording will be transcribed and then also deleted. All other data will be anonymized before achieving or sharing.
"""


def seed_instructions(apps, schema_editor):
    InstructionsPage = apps.get_model("usabilityTest", "InstructionsPage")
    InstructionsPage.objects.update_or_create(
        key="general_instructions",
        defaults={
            "title": "Instructions",
            "content_md": DEFAULT_INSTRUCTIONS_MD,
        },
    )


def unseed_instructions(apps, schema_editor):
    InstructionsPage = apps.get_model("usabilityTest", "InstructionsPage")
    InstructionsPage.objects.filter(key="general_instructions").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usabilityTest", "0006_markdown_all_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="InstructionsPage",
            fields=[
                ("key", models.CharField(default="general_instructions", max_length=64, primary_key=True, serialize=False)),
                ("title", models.CharField(default="Instructions", max_length=128)),
                ("content_md", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Instructions page",
                "verbose_name_plural": "Instructions pages",
            },
        ),
        migrations.RunPython(seed_instructions, unseed_instructions),
    ]
