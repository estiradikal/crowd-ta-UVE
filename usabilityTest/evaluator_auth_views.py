from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import EvaluatorSignUpForm
from .models import EvaluatorProfile

EVALUATORS_GROUP = 'Evaluators'


def _next_url(request):
    url = request.POST.get('next') or request.GET.get('next') or ''
    if url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}):
        return url
    return '/admin-panel/'


def _render_auth(request, login_form, signup_form, mode, status=200):
    return render(request, 'evaluation/auth.html', {
        'login_form': login_form,
        'signup_form': signup_form,
        'mode': mode,
        'next': _next_url(request),
    }, status=status)


def panel_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(_next_url(request))

    login_form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        if login_form.is_valid():
            user = login_form.get_user()
            if user.is_staff:
                login(request, user)
                return redirect(_next_url(request))
            login_form.add_error(None, 'This account does not have access to the evaluation panel.')
        return _render_auth(request, login_form, EvaluatorSignUpForm(), 'login', status=400)

    return _render_auth(request, login_form, EvaluatorSignUpForm(), 'login')


def panel_signup(request):
    if request.method != 'POST':
        return redirect('/admin-panel/login/?mode=signup')

    signup_form = EvaluatorSignUpForm(request.POST, request.FILES)
    if not signup_form.is_valid():
        return _render_auth(request, AuthenticationForm(request), signup_form, 'signup', status=400)

    user = signup_form.save(commit=False)
    # El panel exige is_staff; los evaluadores no reciben permisos sobre el admin de Django
    user.is_staff = True
    user.save()
    group, _ = Group.objects.get_or_create(name=EVALUATORS_GROUP)
    user.groups.add(group)
    EvaluatorProfile.objects.create(
        user=user,
        photo=signup_form.cleaned_data.get('photo'),
        avatar_url=signup_form.cleaned_data.get('avatar_url', ''),
    )

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f'Welcome, {user.first_name}! Your evaluator account is ready.')
    return redirect('/admin-panel/')
