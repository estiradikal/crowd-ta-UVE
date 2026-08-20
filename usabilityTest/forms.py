from django import forms
from .models import SubjectProfile
from django_countries.fields import CountryField

GENDER_CHOICES = (('', '---------'), ('M', 'Male'), ('F', 'Female'), ('Other', 'Other'))
TRUE_FALSE_CHOICES = (('', '---------'), (True, 'Yes'), (False, 'No'))

class SubjectProfileForm(forms.ModelForm):
    age = forms.IntegerField(
        label='Age',
        widget=forms.NumberInput(attrs={'placeholder': 'e.g., 25'})
    )
    gender = forms.ChoiceField(
        required=True,
        choices=GENDER_CHOICES,
        label='Gender',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # CountryField sin argumentos (el label se tomará del modelo o de Meta)
    birth_country = CountryField()
    residence_country = CountryField()
    mother_tongue = forms.CharField(
        max_length=32,
        required=True,
        label='Mother Tongue',
        widget=forms.TextInput(attrs={'placeholder': 'e.g., English'})
    )
    Do_you_speak_English = forms.ChoiceField(
        required=True,
        choices=TRUE_FALSE_CHOICES,
        label='Do you speak English?',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    knowledge_on_usability = forms.ChoiceField(
        required=True,
        choices=TRUE_FALSE_CHOICES,
        label='Do you have any knowledge on usability testing?',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    participated_before = forms.ChoiceField(
        required=True,
        choices=TRUE_FALSE_CHOICES,
        label='Have you participated before in a usability test?',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

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
        # Valores iniciales (se aplican al mostrar el formulario)
        initial = {
            'age': 25,
            'gender': 'M',
            'birth_country': 'US',
            'residence_country': 'US',
            'mother_tongue': 'English',
            'Do_you_speak_English': True,
            'knowledge_on_usability': False,
            'participated_before': False,
        }