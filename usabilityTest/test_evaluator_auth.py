import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import EvaluatorProfile

AVATAR = 'https://api.dicebear.com/9.x/adventurer/svg?seed=abc'
# GIF de 1x1 píxel para probar la subida de foto
TINY_GIF = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00'
            b',\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')


def signup_data(**overrides):
    data = {
        'first_name': 'Ana', 'last_name': 'Perez', 'email': 'ana@example.org',
        'username': 'ana', 'password1': 'Clave-Segura-2026', 'password2': 'Clave-Segura-2026',
        'avatar_url': AVATAR,
    }
    data.update(overrides)
    return data


class EvaluatorAuthTests(TestCase):
    def test_panel_redirects_anonymous_users_to_panel_login(self):
        response = self.client.get('/admin-panel/')
        self.assertRedirects(response, '/admin-panel/login/?next=/admin-panel/', fetch_redirect_response=False)

    def test_login_page_renders(self):
        response = self.client.get('/admin-panel/login/')
        self.assertContains(response, 'Create account')
        self.assertContains(response, 'Evaluator')

    def test_signup_creates_staff_evaluator_and_logs_in(self):
        response = self.client.post('/admin-panel/signup/', signup_data())
        self.assertRedirects(response, '/admin-panel/', fetch_redirect_response=False)
        user = User.objects.get(username='ana')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.groups.filter(name='Evaluators').exists())
        self.assertEqual(user.evaluator_profile.role, EvaluatorProfile.ROLE_EVALUATOR)
        self.assertEqual(user.evaluator_profile.image_url, AVATAR)
        self.assertEqual(self.client.get('/admin-panel/').status_code, 200)

    def test_username_must_be_unique_ignoring_case(self):
        User.objects.create_user(username='Ana', password='x')
        response = self.client.post('/admin-panel/signup/', signup_data(username='ana'))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'already taken', status_code=400)
        self.assertEqual(User.objects.filter(username__iexact='ana').count(), 1)

    def test_rejects_avatar_from_other_hosts(self):
        response = self.client.post('/admin-panel/signup/', signup_data(avatar_url='https://evil.example/a.svg'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='ana').exists())

    def test_signup_with_uploaded_photo(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            photo = SimpleUploadedFile('me.gif', TINY_GIF, content_type='image/gif')
            self.client.post('/admin-panel/signup/', signup_data(avatar_url='', photo=photo))
            profile = User.objects.get(username='ana').evaluator_profile
            self.assertTrue(profile.image_url.startswith('/media/avatars/'))

    def test_login_and_logout_return_to_panel_login(self):
        User.objects.create_user(username='eva', password='Clave-Segura-2026', is_staff=True)
        response = self.client.post('/admin-panel/login/', {'username': 'eva', 'password': 'Clave-Segura-2026'})
        self.assertRedirects(response, '/admin-panel/', fetch_redirect_response=False)
        response = self.client.post('/logout/')
        self.assertRedirects(response, '/admin-panel/login/', fetch_redirect_response=False)

    def test_non_staff_cannot_log_into_panel(self):
        User.objects.create_user(username='tester', password='Clave-Segura-2026')
        response = self.client.post('/admin-panel/login/', {'username': 'tester', 'password': 'Clave-Segura-2026'})
        self.assertContains(response, 'does not have access', status_code=400)


class PanelSettingsTests(TestCase):
    def setUp(self):
        # Como el admin real: creado por consola, sin nombre ni correo
        self.user = User.objects.create_superuser('jefa', '', 'Clave-Segura-2026')
        self.client.force_login(self.user)

    def save(self, **overrides):
        """Envía el formulario completo de Configuración, como lo hace el navegador."""
        data = {'tab': 'account', 'first_name': '', 'last_name': '', 'email': '', 'avatar_url': '',
                'old_password': '', 'new_password1': '', 'new_password2': '',
                'language': 'en', 'accent_color': 'blue', 'shortcuts_enabled': 'on',
                'key_play_pause': ' ', 'key_mark_start': 's', 'key_mark_end': 'e',
                'key_rewind': 'arrowleft', 'key_forward': 'arrowright', 'key_toggle_guide': '?'}
        data.update(overrides)
        return self.client.post('/admin-panel/config/', {k: v for k, v in data.items() if v is not None})

    def profile(self):
        return EvaluatorProfile.objects.get(user=self.user)

    def test_settings_page_has_three_tabs_and_creates_profile(self):
        response = self.client.get('/admin-panel/config/')
        self.assertEqual(response.status_code, 200)
        for text in ('My account', 'Preferences', 'Keyboard shortcuts', 'Change password', 'Save changes'):
            self.assertContains(response, text)
        self.assertNotContains(response, 'System Information')
        self.assertTrue(EvaluatorProfile.objects.filter(user=self.user).exists())

    def test_avatar_and_color_save_together_without_name_or_email(self):
        response = self.save(avatar_url=AVATAR, accent_color='green', tab='preferences')
        self.assertRedirects(response, '/admin-panel/config/?tab=preferences', fetch_redirect_response=False)
        profile = self.profile()
        self.assertEqual(profile.image_url, AVATAR)
        self.assertEqual(profile.accent_color, 'green')
        page = self.client.get('/admin-panel/')
        self.assertContains(page, AVATAR)
        self.assertContains(page, '--accent-light: #16a34a')

    def test_saving_without_choosing_avatar_keeps_current_one(self):
        self.save(avatar_url=AVATAR)
        self.save(avatar_url='', accent_color='red')
        self.assertEqual(self.profile().image_url, AVATAR)

    def test_language_translates_the_panel(self):
        self.save(language='es')
        page = self.client.get('/admin-panel/')
        self.assertContains(page, 'Cerrar sesión')
        self.assertContains(page, 'Evaluaciones recientes')
        self.assertContains(page, '<html lang="es"')
        self.assertContains(self.client.get('/admin-panel/config/'), 'Atajos de teclado')
        self.save(language='de')
        self.assertContains(self.client.get('/admin-panel/videos/'), 'Videoliste')
        self.save(language='fr')
        self.assertContains(self.client.get('/admin-panel/reportes/'), 'Rapports')

    def test_rejects_unknown_language_and_color(self):
        self.client.get('/admin-panel/config/')
        response = self.save(language='xx', accent_color='neon')
        self.assertEqual(response.status_code, 400)
        self.assertEqual((self.profile().language, self.profile().accent_color), ('en', 'blue'))

    def test_account_updates_name_and_email(self):
        self.save(first_name='Ana', last_name='Ruiz', email='ana@example.org')
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name, self.user.email), ('Ana', 'Ruiz', 'ana@example.org'))

    def test_invalid_email_blocks_save_and_shows_account_tab(self):
        response = self.save(email='no-es-correo', accent_color='red')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context['active_tab'], 'account')
        self.assertEqual(self.profile().accent_color, 'blue')

    def test_password_change_keeps_session(self):
        self.save(old_password='Clave-Segura-2026', new_password1='Otra-Clave-2027', new_password2='Otra-Clave-2027')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Otra-Clave-2027'))
        self.assertEqual(self.client.get('/admin-panel/').status_code, 200)

    def test_password_change_rejects_wrong_current_password(self):
        response = self.save(old_password='equivocada', new_password1='Otra-Clave-2027', new_password2='Otra-Clave-2027')
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Clave-Segura-2026'))

    def test_shortcuts_are_saved_and_used_in_the_panel(self):
        self.save(key_mark_start='a', key_rewind='j')
        profile = self.profile()
        self.assertEqual(profile.shortcuts['mark_start'], 'a')
        self.assertEqual(profile.shortcuts['play_pause'], ' ')
        page = self.client.get('/admin-panel/')
        self.assertContains(page, '"mark_start": "a"')
        self.assertContains(page, 'PANEL_SHORTCUTS_ENABLED = true')

    def test_shortcuts_reject_duplicates(self):
        response = self.save(key_mark_end='s')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context['active_tab'], 'shortcuts')
        self.assertContains(response, 'already used', status_code=400)

    def test_shortcuts_can_be_disabled(self):
        self.save(shortcuts_enabled=None)
        self.assertContains(self.client.get('/admin-panel/'), 'PANEL_SHORTCUTS_ENABLED = false')
