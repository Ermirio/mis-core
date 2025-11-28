@echo off
echo ==========================================
echo MATANDO PROCESSOS PYTHON ZUMBIS...
echo ==========================================
taskkill /F /IM python.exe /T
echo.
echo Processos mortos. Aguardando 3 segundos...
timeout /t 3 /nobreak >nul

echo.
echo ==========================================
echo REINICIANDO SISTEMA...
echo ==========================================

start "Django Backend" cmd /k "cd backend-django && py manage.py runserver 0.0.0.0:8000"
start "Flask Backend" cmd /k "cd backend-flask && py app.py"
start "Coletor" cmd /k "cd coletor && py coletor.py"

echo.
echo Sistema reiniciado! Verifique as novas janelas.
pause
