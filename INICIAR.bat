@echo off
cd /d "%~dp0"
python manage.py migrate
if errorlevel 1 goto error
python manage.py runserver
goto fin
:error
echo No se pudo iniciar. Revisa el error anterior y las dependencias.
:fin
pause
