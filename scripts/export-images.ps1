# =============================================================================
# export-images.ps1 — Exporta imagens MIS Core para deploy offline (rede OT)
# Máquina de DESENVOLVIMENTO — Windows (PowerShell)
#
# Uso:
#   cd <raiz-do-projeto>
#   .\scripts\export-images.ps1
#
#   Para definir versão:
#   $env:MIS_VERSION="1.5"; .\scripts\export-images.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Configuração -----------------------------------------------------------
$VERSION    = if ($env:MIS_VERSION) { $env:MIS_VERSION } else { "dev" }
$OUTPUT_DIR = ".\docker-images"
$OUTPUT_TAR = "$OUTPUT_DIR\mis-core-images.tar"
$OUTPUT_GZ  = "$OUTPUT_TAR.gz"

$APP_IMAGES = @(
    "mis-core-django:$VERSION"
    "mis-core-fastapi:$VERSION"
    "mis-core-frontend:$VERSION"
    "mis-core-coletor:$VERSION"
)

$INFRA_IMAGES = @(
    "mysql:8.0"
    "influxdb:1.8-alpine"
    "chronograf:1.8"
    "grafana/grafana:10.4.2"
    "nodered/node-red:3.1.9"
    "emqx/emqx:5.6.1"
    "portainer/portainer-ce:2.39.5-alpine"
)

Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  MIS Core — Exportação para Deploy Offline" -ForegroundColor Cyan
Write-Host "  Versão: $VERSION" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""

# --- Verificações -----------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERRO: docker não encontrado no PATH." -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $OUTPUT_DIR | Out-Null

# --- Build ------------------------------------------------------------------
Write-Host "[1/4] Buildando imagens de aplicação..." -ForegroundColor Yellow
Write-Host ""
docker compose build
Write-Host ""

# --- Pull infraestrutura ----------------------------------------------------
Write-Host "[2/4] Baixando imagens de infraestrutura..." -ForegroundColor Yellow
foreach ($img in $INFRA_IMAGES) {
    Write-Host "  -> docker pull $img"
    docker pull $img
}
Write-Host ""

# --- Verificar imagens ------------------------------------------------------
Write-Host "[3/4] Verificando imagens..." -ForegroundColor Yellow
$ALL_IMAGES = $APP_IMAGES + $INFRA_IMAGES
$MISSING = 0
foreach ($img in $ALL_IMAGES) {
    $exists = docker image inspect $img 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK  $img" -ForegroundColor Green
    } else {
        Write-Host "  XX  $img  NAO ENCONTRADA" -ForegroundColor Red
        $MISSING++
    }
}
if ($MISSING -gt 0) {
    Write-Host ""
    Write-Host "ERRO: $MISSING imagem(ns) nao encontrada(s). Abortando." -ForegroundColor Red
    exit 1
}
Write-Host ""

# --- Exportar ---------------------------------------------------------------
Write-Host "[4/4] Exportando imagens para $OUTPUT_TAR ..." -ForegroundColor Yellow
Write-Host "      (pode levar varios minutos)"
Write-Host ""

docker save $ALL_IMAGES -o $OUTPUT_TAR

# Compressão via 7-Zip (preferido) ou PowerShell nativo
Write-Host "  -> Comprimindo..."
if (Get-Command 7z -ErrorAction SilentlyContinue) {
    7z a -tgzip "$OUTPUT_GZ" "$OUTPUT_TAR" | Out-Null
    Remove-Item $OUTPUT_TAR
} else {
    # PowerShell nativo (mais lento, mas sem dependência externa)
    $src  = (Resolve-Path $OUTPUT_TAR).Path
    $dest = (Join-Path (Resolve-Path $OUTPUT_DIR).Path "mis-core-images.tar.gz")
    $fs   = [System.IO.File]::OpenRead($src)
    $gs   = [System.IO.File]::Create($dest)
    $gz   = New-Object System.IO.Compression.GZipStream($gs, [System.IO.Compression.CompressionMode]::Compress)
    $fs.CopyTo($gz)
    $gz.Close(); $gs.Close(); $fs.Close()
    Remove-Item $OUTPUT_TAR
}

$FILE_SIZE = [math]::Round((Get-Item $OUTPUT_GZ).Length / 1GB, 2)

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Green
Write-Host "  EXPORTACAO CONCLUIDA" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Arquivo : $OUTPUT_GZ"
Write-Host "  Tamanho : $FILE_SIZE GB"
Write-Host "  Versao  : $VERSION"
Write-Host ""
Write-Host "  Copie para o pendrive/servidor OT:" -ForegroundColor Yellow
Write-Host "    docker-images\mis-core-images.tar.gz"
Write-Host "    mis-core-offline\docker-compose.yml"
Write-Host "    mis-core-offline\.env.example"
Write-Host "    mis-core-offline\import-images.sh"
Write-Host ""
