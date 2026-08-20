# usabilityTest/forms.py

from django import forms
from .models import SubjectProfile
from django_countries.fields import CountryField

GENDER_CHOICES = (('',''), ('M', 'male'), ('F', 'female'), ('Other', 'other'))
TRUE_FALSE_CHOICES = (('',''), (True, 'Yes'), (False, 'No'))

class SubjectProfileForm(forms.ModelForm):
    class Meta:
        model = SubjectProfile
        fields = [
            'age', 'gender', 'birth_country', 'residence_country',
            'mother_tongue', 'Do_you_speak_English',
            'knowledge_on_usability', 'participated_before',
            'payment_id', 'workerId', 'campId', 'groupId'
        ]
        widgets = {
            'payment_id': forms.HiddenInput(),
            'workerId': forms.HiddenInput(),
            'campId': forms.HiddenInput(),
            'groupId': forms.HiddenInput(),
        }