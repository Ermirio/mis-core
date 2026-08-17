Write-Host "Iniciando deploy offline..."

if (-not (Test-Path "mis-core-images.tar")) {
    Write-Host "Erro: Arquivo 'mis-core-images.tar' nao encontrado nesta pasta."
    exit 1
}

Write-Host "Carregando imagens para o Docker (Isso pode demorar)..."
docker load -i mis-core-images.tar

# Verification step
Write-Host "Imagens carregadas:"
docker images | findstr "mis-core"

Write-Host "Subindo os servicos..."
docker compose up -d

Write-Host "Deploy Concluido!"
Write-Host "Frontend:   http://localhost:81"
Write-Host "Django:     http://localhost:8001"
Write-Host "Flask:      http://localhost:5002"
Write-Host "FastAPI v2: http://localhost:8002/api/v2/docs"
Write-Host "Coletor:    Rodando (Servico de Background - Sem URL)"
