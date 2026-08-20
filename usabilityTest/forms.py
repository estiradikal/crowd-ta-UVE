# usabilityTest/forms.py

from django import forms
from .models import SubjectProfile
from django_countries.fields import CountryField

GENDER_CHOICES = (('',''), ('M', 'male'), ('F', 'female'), ('Other', 'other'))
TRUE_FALSE_CHOICES = (('',''), (True, 'Yes'), (False, 'No'))

class SubjectProfileForm(forms.ModelForm):
    age = forms.IntegerField()
    gender = forms.ChoiceField(required=True, choices=GENDER_CHOICES, initial=None)
    birth_country = CountryField()
    residence_country = CountryField()
    mother_tongue = forms.CharField(max_length=32, required=True, label="Mother Tongue")
    Do_you_speak_English = forms.ChoiceField(required=True, choices=TRUE_FALSE_CHOICES, initial=None, label="Do you speak English?")
    knowledge_on_usability = forms.ChoiceField(required=True, choices=TRUE_FALSE_CHOICES, initial=None, label="Do you have any knowledge on usability testing?")
    participated_before = forms.ChoiceField(required=True, initial=None, choices=TRUE_FALSE_CHOICES, label="Have you participated before in a usability test?")

    class Meta:
        model = SubjectProfile
        fields = [
            'age', 'gender', 'birth_country', 'residence_country',
            'mother_tongue', 'Do_you_speak_English',
            'knowledge_on_usability', 'participated_before',
            'payment_id', 'workerId', 'groupId'   # agregados
        ]
        widgets = {
            'payment_id': forms.HiddenInput(),
            'workerId': forms.HiddenInput(),
            'groupId': forms.HiddenInput(),
        }