
# Kill existing processes
$processes = Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -like '*manage.py runserver*' -or $_.CommandLine -like '*run.py*' -or $_.CommandLine -like '*coletor.py*'}
foreach ($p in $processes) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Killed process $($p.ProcessId)"
}

# Start Django on 8001
$djangoCmd = "Start-Process python 'manage.py runserver 0.0.0.0:8001' -WorkingDirectory 'C:\Users\ermir\Documents\GitHub\projeto-monitoramento-industrial-completo\backend-django' -WindowStyle Minimized"
Invoke-Expression $djangoCmd
Write-Host "Started Django on 8001"

# Start Flask on 5000
$flaskCmd = "Start-Process python 'run.py' -WorkingDirectory 'C:\Users\ermir\Documents\GitHub\projeto-monitoramento-industrial-completo\backend-flask' -WindowStyle Minimized"
Invoke-Expression $flaskCmd
Write-Host "Started Flask on 5000"

# Start Coletor
$coletorCmd = "Start-Process python 'coletor.py' -WorkingDirectory 'C:\Users\ermir\Documents\GitHub\projeto-monitoramento-industrial-completo\coletor' -WindowStyle Minimized"
Invoke-Expression $coletorCmd
Write-Host "Started Coletor"
