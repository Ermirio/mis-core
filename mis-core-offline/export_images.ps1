# =============================================================================
# export_images.ps1 - Builda e exporta imagens MIS Core para deploy offline OT
#
# Executar na maquina de desenvolvimento, a partir desta pasta ou da raiz:
#   powershell -ExecutionPolicy Bypass -File .\mis-core-offline\export_images.ps1
#   powershell -ExecutionPolicy Bypass -File .\mis-core-offline\export_images.ps1 -Version 2026.05.09
#
# Saida gerada dentro de mis-core-offline:
#   mis-core-images-<VERSION>.tar.gz
#   mis-core-images-<VERSION>.sha256
#   mis-core-images-<VERSION>.manifest.txt
# =============================================================================

param(
    [string]$Version = "",
    [switch]$SkipInfraPull
)

$ErrorActionPreference = "Stop"

$OfflineDir = $PSScriptRoot
$RootDir = Split-Path $OfflineDir -Parent
Set-Location $RootDir

function Get-GitHash {
    try {
        $hash = (git rev-parse --short HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $hash) { return $hash.Trim() }
    } catch {}
    return "no-git"
}

if (-not $Version) {
    if ($env:MIS_VERSION) {
        $Version = $env:MIS_VERSION
    } else {
        $Version = "dev"
    }
}

$GitHash = Get-GitHash
$BuildTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$env:MIS_VERSION = $Version
$env:MIS_GIT_HASH = $GitHash
$env:MIS_BUILD_TIME = $BuildTime

$AppImages = @(
    "mis-core-frontend:$Version",
    "mis-core-django:$Version",
    "mis-core-fastapi:$Version",
    "mis-core-coletor:$Version",
    # Imagem custom de Node-RED com TODOS os nós do DEV. Buildada
    # logo abaixo a partir de mis-core-offline/node-red/.
    "mis-core-nodered:$Version"
)

# `nodered/node-red:3.1.9` saiu daqui: substituído pela `mis-core-nodered`
# custom que estende-o, então a base fica embarcada via FROM.
$InfraImages = @(
    "mysql:8.0",
    "influxdb:1.8-alpine",
    "chronograf:1.8",
    "grafana/grafana:10.4.2",
    "emqx/emqx:5.6.1",
    "portainer/portainer-ce:2.39.5-alpine"
)

$AllImages = $AppImages + $InfraImages
$Tar = Join-Path $OfflineDir "mis-core-images-$Version.tar"
$TarGz = "$Tar.gz"
$ShaFile = Join-Path $OfflineDir "mis-core-images-$Version.sha256"
$ManifestFile = Join-Path $OfflineDir "mis-core-images-$Version.manifest.txt"
$ObsoleteOverlays = @(
    (Join-Path $OfflineDir "mis-core-django-$Version.tar.gz"),
    (Join-Path $OfflineDir "mis-core-django-$Version.sha256"),
    (Join-Path $OfflineDir "mis-core-nodered-$Version.tar.gz"),
    (Join-Path $OfflineDir "mis-core-nodered-$Version.sha256")
)

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  MIS Core - Build e Export Offline OT" -ForegroundColor Cyan
Write-Host "  Version    : $Version" -ForegroundColor Cyan
Write-Host "  Git hash   : $GitHash" -ForegroundColor Cyan
Write-Host "  Build time : $BuildTime" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker nao encontrado no PATH."
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

$BaselineNodeRedDependencies = [ordered]@{
    "@aaqu/node-red-modbus-tcp" = "~0.4.1"
    "@energyweb/node-red-contrib-green-proof-worker" = "~2.5.1"
    "@flowfuse/node-red-dashboard" = "~1.30.2"
    "industrialcomm" = "~1.1.6"
    "node-red-contrib-cip-st-ethernet-ip" = "~2.0.3"
    "node-red-contrib-consecutive-queue-gate" = "~1.1.1"
    "node-red-contrib-cron-plus" = "~2.2.4"
    "node-red-contrib-float" = "~1.0.3"
    "node-red-contrib-influxdb" = "~0.7.0"
    "node-red-contrib-modbus" = "~5.45.2"
    "node-red-contrib-mssql" = "~0.0.7"
    "node-red-contrib-omron-fins" = "~0.5.0"
    "node-red-contrib-opcua" = "~0.2.348"
    "node-red-contrib-originalpid" = "~0.3.1"
    "node-red-contrib-pccc" = "~1.0.2"
    "node-red-contrib-postgresql" = "~0.15.4"
    "node-red-contrib-s7" = "~3.1.1"
    "node-red-contrib-ui-led" = "~0.4.11"
    "node-red-contrib-ui-level" = "~0.1.46"
    "node-red-contrib-ui-navbar" = "~1.0.11"
    "node-red-contrib-ui-state-trail" = "~1.0.2"
    "node-red-dashboard" = "~3.6.6"
    "node-red-mysql-r2" = "~1.3.0"
    "node-red-node-mysql" = "~3.0.0"
    "node-red-node-sqlite" = "~1.1.1"
    "node-red-node-ui-table" = "~0.4.5"
    "plcindustry" = "~2.1.1"
}

function New-NodeRedOfflinePackage([object]$DevDependencies = $null) {
    $deps = [ordered]@{}
    foreach ($key in $BaselineNodeRedDependencies.Keys) {
        $deps[$key] = $BaselineNodeRedDependencies[$key]
    }

    if ($DevDependencies) {
        foreach ($prop in ($DevDependencies.PSObject.Properties | Sort-Object Name)) {
            if ($prop.Name -and -not $deps.Contains($prop.Name)) {
                $deps[$prop.Name] = [string]$prop.Value
            }
        }
    }

    return [ordered]@{
        name = "node-red-project"
        description = "MIS Core Node-RED - gerado por export_images.ps1"
        version = "0.0.1"
        private = $true
        dependencies = $deps
    }
}

Write-Host "[1/6] Buildando imagens da aplicacao..." -ForegroundColor Yellow
docker compose build frontend django fastapi coletor

Write-Host ""
Write-Host "[2/6] Sincronizando config Node-RED + buildando imagem custom..." -ForegroundColor Yellow
# --------------------------------------------------------------------------
# Empacotamento autossuficiente do Node-RED:
#  (a) settings.js canônico de ../node-red/settings.js → mis-core-offline/node-red/
#  (b) package.json EXTRAÍDO do container DEV (captura tudo que foi
#      instalado via palette manager) → mis-core-offline/node-red/
#  (c) build de mis-core-nodered:$Version a partir desta pasta
# Sem isso, o OT teria a imagem oficial do Node-RED sem os nós e sem
# nosso settings.js (adminAuth/Projects/contextStorage/debug).
# --------------------------------------------------------------------------
$NrSrcSettings  = Join-Path $RootDir 'node-red\settings.js'
$NrDstDir       = Join-Path $OfflineDir 'node-red'
$NrDstSettings  = Join-Path $NrDstDir 'settings.js'
$NrDstPackage   = Join-Path $NrDstDir 'package.json'

if (-not (Test-Path $NrSrcSettings)) {
    throw "settings.js fonte não encontrado em $NrSrcSettings"
}
Copy-Item -Force $NrSrcSettings $NrDstSettings
Write-Host ("  settings.js copiado: {0}" -f (Split-Path $NrSrcSettings -Leaf)) -ForegroundColor Green

# Extrai o package.json do container DEV em execução para acrescentar nós
# instalados via palette manager. O baseline industrial acima sempre entra,
# mesmo se o DEV estiver incompleto.
$nrContainerOk = $false
try {
    docker exec mis-core-nodered cat /data/package.json *> $env:TEMP\mis_nr_pkg.json
    if ($LASTEXITCODE -eq 0) { $nrContainerOk = $true }
} catch {}

$devDependencies = $null
if ($nrContainerOk) {
    try {
        $pkg = Get-Content $env:TEMP\mis_nr_pkg.json -Raw | ConvertFrom-Json
        if ($pkg.dependencies) {
            $devDependencies = $pkg.dependencies
            $deps = @($pkg.dependencies.PSObject.Properties).Count
            Write-Host ("  package.json DEV lido: {0} dependencia(s)" -f $deps) -ForegroundColor Green
        } else {
            Write-Host "  AVISO: package.json DEV sem dependencies. Usando baseline industrial." -ForegroundColor Yellow
        }
    } catch {
        Write-Host ("  AVISO: nao consegui parsear package.json do DEV: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
        Write-Host "  Usando baseline industrial obrigatorio." -ForegroundColor Yellow
    } finally {
        Remove-Item $env:TEMP\mis_nr_pkg.json -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "  AVISO: container 'mis-core-nodered' nao esta rodando. Usando baseline industrial." -ForegroundColor Yellow
    Write-Host "         (Suba o stack DEV antes apenas se quiser capturar nos extras)" -ForegroundColor Yellow
}

$offlinePkg = New-NodeRedOfflinePackage -DevDependencies $devDependencies
$offlinePkg | ConvertTo-Json -Depth 10 | Out-File -Encoding utf8 $NrDstPackage
$finalDeps = @($offlinePkg.dependencies.Keys).Count
Write-Host ("  package.json final: {0} dependencia(s), incluindo Modbus/MySQL/Influx/Dashboard" -f $finalDeps) -ForegroundColor Green

# Build da imagem custom
Write-Host "  Buildando mis-core-nodered:$Version..."
docker build -t "mis-core-nodered:$Version" $NrDstDir
if ($LASTEXITCODE -ne 0) {
    throw "Falha no build de mis-core-nodered:$Version"
}
Write-Host "  mis-core-nodered:$Version OK" -ForegroundColor Green

Write-Host ""
Write-Host "[3/6] Verificando imagens de infraestrutura..." -ForegroundColor Yellow
foreach ($img in $InfraImages) {
    if (-not (Test-DockerImage $img)) {
        if ($SkipInfraPull) {
            throw "Imagem de infraestrutura ausente: $img. Rode sem -SkipInfraPull em ambiente com internet."
        }
        Write-Host "  Baixando $img..." -ForegroundColor Yellow
        docker pull $img
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao baixar $img"
        }
    } else {
        Write-Host "  OK $img" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "[4/6] Validando tags da aplicacao..." -ForegroundColor Yellow
$Missing = 0
foreach ($img in $AppImages) {
    if (-not (Test-DockerImage $img)) {
        Write-Host "  X $img nao encontrada" -ForegroundColor Red
        $Missing++
        continue
    }
    $inspectJson = docker image inspect $img | ConvertFrom-Json
    $labelVersion = $inspectJson[0].Config.Labels.'org.opencontainers.image.version'
    if ($labelVersion -and $labelVersion -ne $Version) {
        Write-Host "  X $img label=$labelVersion esperado=$Version" -ForegroundColor Red
        $Missing++
    } else {
        Write-Host "  OK $img" -ForegroundColor Green
    }
}
if ($Missing -gt 0) {
    throw "$Missing imagem(ns) divergente(s). Abortando exportacao."
}

Write-Host ""
Write-Host "[5/6] Salvando pacote em $TarGz..." -ForegroundColor Yellow
if (Test-Path $Tar) { Remove-Item $Tar -Force }
if (Test-Path $TarGz) { Remove-Item $TarGz -Force }
docker save -o $Tar @AllImages

Add-Type -AssemblyName System.IO.Compression.FileSystem
$inputStream = [System.IO.File]::OpenRead($Tar)
$outputStream = [System.IO.File]::Create($TarGz)
$gzipStream = New-Object System.IO.Compression.GZipStream($outputStream, [System.IO.Compression.CompressionMode]::Compress)
$inputStream.CopyTo($gzipStream)
$gzipStream.Dispose()
$outputStream.Dispose()
$inputStream.Dispose()
for ($attempt = 1; $attempt -le 10; $attempt++) {
    try {
        Remove-Item $Tar -Force
        break
    } catch {
        if ($attempt -eq 10) {
            Write-Host "  Aviso: nao foi possivel remover $Tar; o pacote .tar.gz ja foi gerado." -ForegroundColor Yellow
        } else {
            Start-Sleep -Seconds 2
        }
    }
}

Write-Host ""
Write-Host "[6/6] Gerando checksum e manifesto..." -ForegroundColor Yellow
$hash = (Get-FileHash $TarGz -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path $TarGz -Leaf)" | Out-File -Encoding ascii $ShaFile

$manifest = @()
$manifest += "MIS Core Offline Image Pack"
$manifest += "version=$Version"
$manifest += "git_hash=$GitHash"
$manifest += "build_time=$BuildTime"
$manifest += "host_target=192.168.70.160:8080"
$manifest += ""
$manifest += "images:"
foreach ($img in $AllImages) {
    $id = docker image inspect $img --format '{{.Id}}'
    $size = docker image inspect $img --format '{{.Size}}'
    $manifest += "- $img id=$id size_bytes=$size"
}
$manifest | Out-File -Encoding ascii $ManifestFile

# Um pacote completo substitui overlays incrementais anteriores. Mantê-los ao
# lado do novo tarball poderia reintroduzir uma imagem antiga no update OT.
foreach ($overlay in $ObsoleteOverlays) {
    if (Test-Path $overlay) {
        Remove-Item -LiteralPath $overlay -Force
        Write-Host "  Overlay antigo removido: $(Split-Path $overlay -Leaf)" -ForegroundColor Yellow
    }
}

$sizeMB = [math]::Round((Get-Item $TarGz).Length / 1MB, 0)

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Green
Write-Host "  PACOTE OFFLINE ATUALIZADO" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Write-Host "  $TarGz ($sizeMB MB)" -ForegroundColor Cyan
Write-Host "  $ShaFile" -ForegroundColor Cyan
Write-Host "  $ManifestFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "Copie a pasta mis-core-offline para o servidor OT e execute:" -ForegroundColor Yellow
Write-Host "  powershell -ExecutionPolicy Bypass -File .\import_images.ps1"
