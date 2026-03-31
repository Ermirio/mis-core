# Script para construir e exportar imagens Docker do MIS v7.0 para servidor offline

Write-Host "Iniciando build das imagens do MIS v7.0..." -ForegroundColor Cyan

# Diretórios
$FrontendPath = ".\Frontend"
$BackendPath = ".\Backend"
$ImagesDir = ".\Imagens_v7.0"

if (-not (Test-Path $ImagesDir)) {
    New-Item -ItemType Directory -Path $ImagesDir | Out-Null
}

Write-Host "Construindo Backend (mis-backend:7.0)..." -ForegroundColor Yellow
docker build -t mis-backend:7.0 $BackendPath

Write-Host "Construindo Frontend (mis-frontend:7.0)..." -ForegroundColor Yellow
docker build -t mis-frontend:7.0 $FrontendPath

Write-Host "Construindo Nginx Proxy (mis-proxy:7.0)..." -ForegroundColor Yellow
docker build -t mis-proxy:7.0 .

Write-Host "Salvando imagens em .tar para offline..." -ForegroundColor Yellow
docker save mis-backend:7.0 -o "$ImagesDir\mis-backend-v7.0.tar"
docker save mis-frontend:7.0 -o "$ImagesDir\mis-frontend-v7.0.tar"
docker save mis-proxy:7.0 -o "$ImagesDir\mis-proxy-v7.0.tar"

Write-Host "Exportação concluída! Os arquivos .tar estão no diretório $ImagesDir" -ForegroundColor Green
