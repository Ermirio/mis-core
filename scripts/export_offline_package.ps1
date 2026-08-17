<#
.SYNOPSIS
    Prepares the offline deployment package for MIS Core.
.DESCRIPTION
    This script:
    1. Creates a 'dist' folder.
    2. Copies necessary configuration files and volumes.
    3. Builds the Docker images (to ensure they match the code).
    4. Saves all required Docker images to a .tar bundle.
.NOTES
    Run from the root of the repository.
#>

$ErrorActionPreference = "Stop"
$DistDir = "dist"
$ImagesDir = "$DistDir\images"

Write-Host ">>> Starting Offline Package Preparation..." -ForegroundColor Cyan

# 1. Prepare Directories
Write-Host "1. Cleaning and creating '$DistDir' directory..."
If (Test-Path $DistDir) { Remove-Item $DistDir -Recurse -Force }
New-Item -ItemType Directory -Path $ImagesDir -Force | Out-Null

# 2. Copy Config Files
Write-Host "2. Copying configuration files..."
Copy-Item "docker-compose.offline.yml" -Destination "$DistDir\docker-compose.yml"
Copy-Item ".env" -Destination "$DistDir\.env"

# Copy Dependent Folders (Configs/Init)
# Maintain directory structure where necessary for the compose volumes to work (e.g. ./mysql-init)
Write-Host "   - Copying mysql-init..."
Copy-Item -Recurse "mysql-init" "$DistDir\mysql-init"

Write-Host "   - Copying proxy-reverse config..."
Copy-Item -Recurse "proxy-reverse" "$DistDir\proxy-reverse"

Write-Host "   - Copying Grafana assets..."
New-Item -ItemType Directory -Path "$DistDir\mis-core\grafana\img" -Force | Out-Null
Copy-Item "mis-core\grafana\img\*" "$DistDir\mis-core\grafana\img\"

Write-Host "   - Copying Node-RED settings..."
New-Item -ItemType Directory -Path "$DistDir\mis-core\node-red" -Force | Out-Null
Copy-Item "mis-core\node-red\settings.js" "$DistDir\mis-core\node-red\settings.js"

# 3. Build Images (Ensure everything is up to date)
Write-Host "3. Building Docker images (this may take a while)..."
docker-compose build

# 3b. Garantir que a imagem do Recipe Monitor existe (build dedicado caso o
#     compose principal não cubra — exige menos atrito em ambientes onde o
#     compose foi rodado parcialmente).
Write-Host "   - Building mis-recipe-intelligent:v1.0 (Recipe Monitor)..."
docker build -t mis-recipe-intelligent:v1.0 ".\mis-change-over\Backend\recipe_monitor_service"

# 4. Save Images
Write-Host "4. Saving Docker images to '$ImagesDir\mis_core_bundle.tar'..."
Write-Host "   (This process can take several minutes due to image sizes)"

$images = @(
    # Third Party
    "mysql:8.0",
    "influxdb:1.8-alpine",
    "redis:7-alpine",                        # NOVO — cache + pub/sub do Recipe Monitor
    "portainer/portainer-ce:latest",
    "n8nio/n8n:latest",
    "grafana/grafana:latest",
    "emqx/emqx:5.8.5",
    "chronograf:1.8",
    "kapacitor:1.5",

    # MIS Core Built Images
    "mis-core-django:v2.0",
    "mis-core-frontend:v2.1",
    "mis-core-proxy:v2.0",
    "mis-core-flask:v2.0",
    "mis-core-coletor:v2.0",
    "mis-core-ai-backend:v1.0",
    "mis-core-ai-frontend:v1.0",
    "mis-core-energy-backend:v1.0",
    "mis-core-energy-frontend:v1.0",
    "mis-core-energy-collector:v1.0",
    "mis-core-changeover-backend:v1.0",
    "mis-core-changeover-frontend:v1.0",
    "mis-core-node-red:v1.0",

    # NOVO — Recipe Monitor (FastAPI + asyncua)
    "mis-recipe-intelligent:v1.0"
)

# Pull third party images to ensure they exist locally (optional, but good safety)
Write-Host "   - Ensuring third-party images are present locally..."
docker pull mysql:8.0
docker pull influxdb:1.8-alpine
docker pull redis:7-alpine                   # NOVO
docker pull portainer/portainer-ce:latest
docker pull n8nio/n8n:latest
docker pull grafana/grafana:latest
docker pull emqx/emqx:5.8.5
docker pull chronograf:1.8
docker pull kapacitor:1.5

# Save command
docker save -o "$ImagesDir\mis_core_bundle.tar" $images

Write-Host "5. Creating Import Script (Linux)..."
$ImportScript = @"
#!/bin/bash
set -e
echo '>>> Starting Import Process...'

echo '1. Loading Docker Images (this may take several minutes)...'
docker load -i images/mis_core_bundle.tar

echo '2. Normalizing line endings (in case of Windows copy)...'
if command -v dos2unix &> /dev/null; then
    dos2unix .env docker-compose.yml 2>/dev/null || true
fi

echo '3. Starting all services (migrations run automatically inside Django entrypoint)...'
docker-compose --env-file .env up -d

echo ''
echo '4. Waiting for services to be healthy...'
# Espera Django saudável (entrypoint roda migrate, collectstatic, cria superuser)
for i in {1..60}; do
    if docker exec mis-changeover-backend curl -fs http://localhost:8000/api/health/ >/dev/null 2>&1; then
        echo '   Django OK (migrations aplicadas)'
        break
    fi
    sleep 2
done

# Espera Recipe Monitor
for i in {1..30}; do
    if docker exec mis-recipe-monitor python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8100/health')\" >/dev/null 2>&1; then
        echo '   Recipe Monitor OK'
        break
    fi
    sleep 2
done

echo ''
echo '>>> Deployment Complete!'
docker-compose ps

echo ''
echo '== Endpoints disponiveis via proxy central =='
echo '  Hub:                http://localhost:\${PROXY_HOST_PORT:-3000}/'
echo '  Change Over (app):  http://localhost:\${PROXY_HOST_PORT:-3000}/mis-change-over/'
echo '  Recipe Monitor API: http://localhost:\${PROXY_HOST_PORT:-3000}/recipe-monitor/health'
echo '  Recipe Monitor WS:  ws://localhost:\${PROXY_HOST_PORT:-3000}/recipe-monitor/ws/linhas/<linha>/stream'
"@
Set-Content -Path "$DistDir\import_and_run.sh" -Value $ImportScript -NoNewline
# Convert to LF line endings just in case, though usually docker handles it. 
# Ideally, run dos2unix on the destination if needed, but bash usually handles simple scripts.

Write-Host ">>> SUCCESS! The offline package is ready in the 'dist' folder."
Write-Host "    Actions:"
Write-Host "    1. Zip/Copy the 'dist' folder to your USB drive or Transfer Agent."
Write-Host "    2. On the offline Ubuntu server, run: chmod +x import_and_run.sh && ./import_and_run.sh"
