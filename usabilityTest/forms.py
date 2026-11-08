from django import forms
from .models import SubjectProfile, Test_Input
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
            'knowledge_on_usability', 'participated_before'
        ]
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


class Test_InputForm(forms.ModelForm):
    class Meta:
        model = Test_Input
        fields = ['campId', 'secret_key', 'application_url']
        widgets = {
            'campId': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., CAMP-001'}),
            'secret_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., my-secret-key'}),
            'application_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
        }
        labels = {
            'campId': 'Campaign ID',
            'secret_key': 'Secret Key',
            'application_url': 'Application URL',
        }


# ---------------------------------------------------------------------------
# Registro de evaluadores del panel
# ---------------------------------------------------------------------------
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

# Avatares generados por DiceBear (https://www.dicebear.com), servidos desde su API
AVATAR_URL_PREFIX = 'https://api.dicebear.com/'


class EvaluatorSignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label='First name')
    last_name = forms.CharField(max_length=150, label='Last name')
    email = forms.EmailField(label='Email')
    photo = forms.ImageField(required=False, label='Profile photo')
    avatar_url = forms.URLField(required=False, max_length=300, widget=forms.HiddenInput)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'email', 'username')

    def clean_username(self):
        username = self.cleaned_data['username']
        # Evita "Javier" y "javier" como usuarios distintos
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already taken. Please choose another one.')
        return username

    def clean_avatar_url(self):
        url = self.cleaned_data.get('avatar_url', '')
        if url and not url.startswith(AVATAR_URL_PREFIX):
            raise forms.ValidationError('Invalid avatar.')
        return url

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > 2 * 1024 * 1024:
            raise forms.ValidationError('The photo must be 2 MB or smaller.')
        return photo


class PreferencesForm(forms.Form):
    language = forms.ChoiceField(choices=[])
    accent_color = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        from .panel_preferences import ACCENT_COLORS, LANGUAGES
        super().__init__(*args, **kwargs)
        self.fields['language'].choices = [(code, name) for code, name, _ in LANGUAGES]
        self.fields['accent_color'].choices = [(key, name) for key, name, _, _ in ACCENT_COLORS]


class AccountForm(forms.ModelForm):
    """Nombre, correo y foto/avatar del usuario que está en sesión."""
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    photo = forms.ImageField(required=False)
    avatar_url = forms.URLField(required=False, max_length=300, widget=forms.HiddenInput)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    clean_avatar_url = EvaluatorSignUpForm.clean_avatar_url
    clean_photo = EvaluatorSignUpForm.clean_photo


class ShortcutsForm(forms.Form):
    shortcuts_enabled = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        from .panel_preferences import SHORTCUT_ACTIONS
        super().__init__(*args, **kwargs)
        for action, *_ in SHORTCUT_ACTIONS:
            # strip=False: la barra espaciadora se guarda como ' '
            self.fields['key_' + action] = forms.CharField(max_length=16, strip=False)

    def clean(self):
        from .panel_preferences import SHORTCUT_ACTIONS, is_valid_shortcut_key
        cleaned = super().clean()
        seen = {}
        for action, *_ in SHORTCUT_ACTIONS:
            name = 'key_' + action
            key = (cleaned.get(name) or '').lower()
            if not is_valid_shortcut_key(key):
                self.add_error(name, 'Invalid key.')
                continue
            if key in seen:
                self.add_error(name, 'This key is already used by another shortcut.')
            seen[key] = action
            cleaned[name] = key
        return cleaned

    def shortcut_keys(self):
        from .panel_preferences import SHORTCUT_ACTIONS
        return {action: self.cleaned_data['key_' + action] for action, *_ in SHORTCUT_ACTIONS}
