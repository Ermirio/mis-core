# =============================================================================
#  import_images.ps1 - Instala MIS Core no servidor OT (offline, Windows)
#
#  COMO USAR:
#    1. Coloque na mesma pasta:
#         mis-core-images-<VERSION>.tar.gz
#         mis-core-images-<VERSION>.sha256  (opcional)
#         docker-compose.yml
#         .env  (se ausente, copiado de .env.example)
#    2. Execute:
#         powershell -ExecutionPolicy Bypass -File .\import_images.ps1
#
#  FLAGS:
#    -NonInteractive   Nao pausa por confirmacao (default: ativado)
#    -SkipLoad         Pula docker load (imagens ja carregadas)
#    -SkipDown         Nao executa docker compose down antes do up
# =============================================================================

param(
    [switch]$Interactive,
    [switch]$SkipLoad,
    [switch]$SkipDown
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
Set-Location $ScriptDir

function Write-Step([string]$msg, [string]$color = "Yellow") {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor $color
}

function Test-DockerImage([string]$Image) {
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker image inspect $Image *> $null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $prevPref
    }
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  MIS Core - Deploy Offline" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# [1] Docker rodando?
# ---------------------------------------------------------------------------
Write-Step "[1/7] Verificando Docker"
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Docker nao esta rodando. Inicie o Docker Desktop e tente novamente." -ForegroundColor Red
    exit 1
}
Write-Host "      Docker OK" -ForegroundColor Green

# ---------------------------------------------------------------------------
# [2] Localizar tarball e .env
# ---------------------------------------------------------------------------
Write-Step "[2/7] Verificando arquivos"

$tarballGz = Get-ChildItem -Filter "mis-core-images-*.tar.gz" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $tarballGz) {
    $tarballGz = Get-Item "mis-core-images.tar.gz" -ErrorAction SilentlyContinue
}
if (-not $tarballGz -and -not $SkipLoad) {
    Write-Host "ERRO: Nenhum arquivo mis-core-images*.tar.gz encontrado." -ForegroundColor Red
    exit 1
}

if ($tarballGz) {
    $sizeMB = [math]::Round($tarballGz.Length / 1MB, 0)
    Write-Host "      Tarball : $($tarballGz.Name) ($sizeMB MB)" -ForegroundColor Green
}

$versionFromFile = ""
if ($tarballGz -and $tarballGz.Name -match "mis-core-images-(.+)\.tar\.gz") {
    $versionFromFile = $Matches[1]
}

if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERRO: docker-compose.yml nao encontrado." -ForegroundColor Red
    exit 1
}
Write-Host "      docker-compose.yml OK" -ForegroundColor Green

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "      .env nao encontrado - copiando .env.example" -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        if ($versionFromFile) {
            (Get-Content ".env") -replace "^MIS_VERSION=.*", "MIS_VERSION=$versionFromFile" |
                Set-Content ".env"
        }
        if ($Interactive) {
            Write-Host ""
            Write-Host "ATENCAO: Edite o .env antes de continuar (senhas, IP, MIS_MODE)." -ForegroundColor Red
            Write-Host "Pressione ENTER para continuar mesmo assim, ou CTRL+C para sair..."
            Read-Host
        } else {
            Write-Host "      Modo nao-interativo: prosseguindo com defaults do .env.example" -ForegroundColor Yellow
        }
    } else {
        Write-Host "ERRO: .env nao encontrado e nao ha .env.example." -ForegroundColor Red
        exit 1
    }
}
Write-Host "      .env OK" -ForegroundColor Green

$envContent = Get-Content ".env"
function Get-EnvValue([string]$key, [string]$default = "") {
    $line = $envContent | Where-Object { $_ -match "^${key}=" } | Select-Object -First 1
    if ($line) { return ($line -replace "^${key}=", "").Trim() }
    return $default
}

$misVersion   = Get-EnvValue "MIS_VERSION" $versionFromFile
$misMode      = Get-EnvValue "MIS_MODE" "production"
$frontendPort = Get-EnvValue "FRONTEND_PORT" "8080"
$serverHost   = Get-EnvValue "SERVER_HOST" "localhost"
$chronoPort   = Get-EnvValue "CHRONOGRAF_PORT" "8889"
$grafanaPort  = Get-EnvValue "GRAFANA_PORT" "3001"
$nodeRedPort  = Get-EnvValue "NODE_RED_PORT" "1880"
$emqxDashPort = Get-EnvValue "EMQX_DASHBOARD_PORT" "18083"

if (-not $misVersion) {
    Write-Host "ERRO: MIS_VERSION nao definido no .env" -ForegroundColor Red
    exit 1
}
Write-Host "      MIS_VERSION = $misVersion" -ForegroundColor Green
Write-Host "      MIS_MODE    = $misMode" -ForegroundColor Green

# ---------------------------------------------------------------------------
# [3] Verificar SHA256
# ---------------------------------------------------------------------------
Write-Step "[3/7] Verificando integridade SHA256"
if ($tarballGz) {
    $shaFile = $tarballGz.Name -replace "\.tar\.gz$", ".sha256"
    if (Test-Path $shaFile) {
        $expectedHash = ((Get-Content $shaFile) -split "\s+")[0].ToLower()
        $actualHash   = (Get-FileHash $tarballGz.FullName -Algorithm SHA256).Hash.ToLower()
        if ($expectedHash -eq $actualHash) {
            Write-Host "      OK Checksum valido" -ForegroundColor Green
        } else {
            Write-Host "      ERRO: CHECKSUM INVALIDO - arquivo corrompido!" -ForegroundColor Red
            exit 2
        }
    } else {
        Write-Host "      Aviso: $shaFile nao encontrado - pulando verificacao." -ForegroundColor Yellow
    }
} else {
    Write-Host "      (Pulado - sem tarball)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# [4] Carregar imagens
# ---------------------------------------------------------------------------
if ($SkipLoad) {
    Write-Step "[4/7] Carregamento de imagens PULADO (-SkipLoad)"
} else {
    Write-Step "[4/7] Carregando imagens Docker (pode levar 2-5 min)"
    Write-Host "      Arquivo: $($tarballGz.Name)"
    & docker load -i $tarballGz.FullName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO: docker load falhou" -ForegroundColor Red
        exit 4
    }

    $nodeRedTarball = Get-Item "mis-core-nodered-$misVersion.tar.gz" -ErrorAction SilentlyContinue
    if (-not $nodeRedTarball) {
        $nodeRedTarball = Get-Item "mis-core-nodered-dev.tar.gz" -ErrorAction SilentlyContinue
    }

    if ($nodeRedTarball) {
        Write-Host "      Overlay Node-RED: $($nodeRedTarball.Name)" -ForegroundColor Yellow
        $nodeRedShaFile = $nodeRedTarball.Name -replace "\.tar\.gz$", ".sha256"
        if (Test-Path $nodeRedShaFile) {
            $expectedNodeRedHash = ((Get-Content $nodeRedShaFile) -split "\s+")[0].ToLower()
            $actualNodeRedHash = (Get-FileHash $nodeRedTarball.FullName -Algorithm SHA256).Hash.ToLower()
            if ($expectedNodeRedHash -ne $actualNodeRedHash) {
                Write-Host "ERRO: CHECKSUM INVALIDO no overlay Node-RED." -ForegroundColor Red
                exit 4
            }
        }
        & docker load -i $nodeRedTarball.FullName
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERRO: docker load do overlay Node-RED falhou" -ForegroundColor Red
            exit 4
        }
    }
}

Write-Host ""
Write-Host "      Imagens disponiveis:" -ForegroundColor Green
docker images --format "table {{.Repository}}:{{.Tag}}`t{{.Size}}" |
    Select-String "mis-core|mysql:|influxdb:|chronograf:|grafana|node-red|emqx|portainer"

# ---------------------------------------------------------------------------
# [5] Validar tags vs MIS_VERSION (apps) + infra
# ---------------------------------------------------------------------------
Write-Step "[5/7] Validando imagens necessarias"
$expectedImages = @(
    "mis-core-frontend:$misVersion",
    "mis-core-django:$misVersion",
    "mis-core-fastapi:$misVersion",
    "mis-core-coletor:$misVersion",
    "mis-core-nodered:$misVersion",
    "mysql:8.0",
    "influxdb:1.8-alpine",
    "chronograf:1.8",
    "grafana/grafana:10.4.2",
    "emqx/emqx:5.6.1",
    "portainer/portainer-ce:2.39.5-alpine"
)
$missing = 0
foreach ($img in $expectedImages) {
    if (Test-DockerImage $img) {
        Write-Host "      OK $img" -ForegroundColor Green
    } else {
        Write-Host "      X  $img  AUSENTE" -ForegroundColor Red
        $missing++
    }
}
if ($missing -gt 0) {
    Write-Host ""
    Write-Host "ERRO: $missing imagem(ns) ausente(s). Refaca o tarball com export_images.ps1." -ForegroundColor Red
    exit 3
}

# ---------------------------------------------------------------------------
# [6] Subir o stack
# ---------------------------------------------------------------------------
Write-Step "[6/7] Subindo servicos"

if (-not $SkipDown) {
    Write-Host "      docker compose down (cleanup)..." -ForegroundColor Yellow
    # Docker escreve progresso normal no stderr. Em PowerShell 5.1 com
    # $ErrorActionPreference=Stop, cada linha de stderr vira NativeCommandError
    # fatal. Solucao: desligar temporariamente para o comando.
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker compose down 2>&1 | Out-Null
    $ErrorActionPreference = $prevPref
    Start-Sleep -Seconds 1
}

Write-Host "      docker compose up -d ..." -ForegroundColor Yellow
# Temporariamente desliga ErrorActionPreference=Stop — docker escreve progresso
# normal no stderr, e em PS 5.1 isso vira NativeCommandError fatal.
$prevPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& docker compose up -d
$upExit = $LASTEXITCODE
$ErrorActionPreference = $prevPref
if ($upExit -ne 0) {
    Write-Host "ERRO: docker compose up falhou (exit=$upExit)" -ForegroundColor Red
    Write-Host "      Diagnostico: docker compose logs" -ForegroundColor Red
    exit 5
}

# ---------------------------------------------------------------------------
# [7] Aguardar healthchecks + validar
# ---------------------------------------------------------------------------
Write-Step "[7/7] Aguardando healthchecks (ate 120s)"

$expectedContainers = @(
    "mis-core-mysql",
    "mis-core-influxdb",
    "mis-core-django",
    "mis-core-fastapi",
    "mis-core-coletor",
    "mis-core-frontend",
    "mis-core-chronograf",
    "mis-core-grafana",
    "mis-core-nodered",
    "mis-core-emqx",
    "mis-core-portainer"
)

$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
    $running = & docker ps --format "{{.Names}}" 2>$null
    $allUp = $true
    foreach ($c in $expectedContainers) {
        if ($running -notcontains $c) { $allUp = $false; break }
    }
    if ($allUp) {
        # Verifica healthchecks dos que possuem
        $unhealthy = & docker ps --filter "health=unhealthy" --format "{{.Names}}" 2>$null
        $starting  = & docker ps --filter "health=starting"  --format "{{.Names}}" 2>$null
        if (-not $unhealthy -and -not $starting) {
            $ready = $true
            break
        }
    }
    Start-Sleep -Seconds 3
    Write-Host "      ... aguardando" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "      Status final:" -ForegroundColor Cyan
& docker compose ps --format "table {{.Name}}\t{{.Image}}\t{{.Status}}"

if (-not $ready) {
    Write-Host ""
    Write-Host "AVISO: Nem todos servicos ficaram saudaveis em 120s." -ForegroundColor Yellow
    Write-Host "       Pode ser normal em primeira inicializacao. Verifique:" -ForegroundColor Yellow
    Write-Host "         docker compose logs -f" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Resumo final
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================================" -ForegroundColor Green
Write-Host "  DEPLOY CONCLUIDO - MIS Core $misVersion (MIS_MODE=$misMode)" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  App local      : http://localhost:$frontendPort/mis-core/" -ForegroundColor Cyan
Write-Host "  App na rede    : http://${serverHost}:$frontendPort/mis-core/" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Admin Django   : http://${serverHost}:$frontendPort/mis-core-admin/"
Write-Host "  FastAPI Docs   : http://${serverHost}:$frontendPort/api/v2/docs"
Write-Host "  Chronograf     : http://${serverHost}:$chronoPort"
Write-Host "  Grafana        : http://${serverHost}:$grafanaPort"
Write-Host "  Node-RED       : http://${serverHost}:$nodeRedPort"
Write-Host "  EMQX Dashboard : http://${serverHost}:$emqxDashPort"
Write-Host "  Portainer      : http://${serverHost}:$frontendPort/mc-portainer/"
Write-Host "  Versao JSON    : http://${serverHost}:$frontendPort/version.json"
Write-Host ""
Write-Host "  Logs em tempo real:  docker compose logs -f"
Write-Host "  Parar stack       :  docker compose down"
Write-Host ""
if (-not $ready) { exit 6 }
