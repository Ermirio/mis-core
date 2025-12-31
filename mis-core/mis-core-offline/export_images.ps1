Write-Host "Iniciando exportacao das imagens Docker..."

$images = @(
    "mis-core-django:v1.0",
    "mis-core-flask:v1.1",
    "mis-core-frontend:v1.0",
    "mis-core-coletor:v1.0",
    "mysql:8.0",
    "influxdb:1.8-alpine",
    "chronograf:1.8",
    "kapacitor:1.5"
)

# Verifica se as imagens existem antes de exportar (opcional, mas bom pra debug)
docker images

Write-Host "Salvando imagens em mis-core-images.tar (Isso pode demorar)..."
docker save -o mis-core-images.tar $images

if (Test-Path "mis-core-images.tar") {
    Write-Host "Sucesso! Arquivo 'mis-core-images.tar' criado."
}
else {
    Write-Host "Erro: Arquivo nao foi criado."
}
