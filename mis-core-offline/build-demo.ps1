# =============================================================================
# build-demo.ps1 - Build do pacote offline com TAG de demonstração.
#
# Gera as MESMAS imagens (não há código diferente entre demo e produção); o
# que muda é o tag e o .env.demo gerado ao lado:
#
#   mis-core-images-<VERSION>-demo.tar.gz
#   .env.demo                   (com MIS_MODE=demo já preenchido)
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\build-demo.ps1
#   powershell -ExecutionPolicy Bypass -File .\build-demo.ps1 -Version 2026.05.13
#
# No servidor offline, basta:
#   cp .env.demo .env
#   docker compose down && docker compose up -d
# =============================================================================

param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$OfflineDir = $PSScriptRoot

if (-not $Version) {
    $stamp = (Get-Date -Format "yyyy.MM.dd")
    $Version = "$stamp-demo"
}

if ($Version -notmatch "demo") {
    $Version = "$Version-demo"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MIS Core - BUILD DEMO" -ForegroundColor Cyan
Write-Host "  Tag: $Version" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Delegar ao export_images.ps1 — mesmo processo de build
& (Join-Path $OfflineDir "export_images.ps1") -Version $Version

# Gerar .env.demo pré-configurado
$envDemo = Join-Path $OfflineDir ".env.demo"
$envExample = Join-Path $OfflineDir ".env.example"

if (-not (Test-Path $envExample)) {
    Write-Host "ATENÇÃO: .env.example não encontrado, pulando geração de .env.demo" -ForegroundColor Yellow
} else {
    $content = Get-Content $envExample -Raw
    $content = $content -replace "MIS_VERSION=dev", "MIS_VERSION=$Version"
    $content = $content -replace "MIS_MODE=production", "MIS_MODE=demo"
    # Senhas placeholders precisam ser substituídas pelo operador — deixa aviso
    [System.IO.File]::WriteAllText($envDemo, $content, [System.Text.Encoding]::UTF8)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  .env.demo gerado em:" -ForegroundColor Green
    Write-Host "    $envDemo" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  No servidor de demo:" -ForegroundColor Yellow
    Write-Host "    cp .env.demo .env" -ForegroundColor White
    Write-Host "    # editar .env e substituir senhas TROQUE-POR-*" -ForegroundColor White
    Write-Host "    docker compose down ; docker compose up -d" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Green
}
