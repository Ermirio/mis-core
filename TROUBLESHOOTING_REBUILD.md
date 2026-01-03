# Guia de Troubleshooting: Aplicar Alterações no MIS-Energy

## 🎯 Problema

As alterações commitadas no branch `mis-hub` (commit `5aa21dca`) não estão aparecendo na aplicação em execução.

## 🔍 Causa Raiz

O Docker Compose não reconstrói automaticamente as imagens quando você faz apenas `docker-compose up`. Mesmo após fazer `git pull` para obter as novas alterações, os containers continuam rodando com as imagens antigas que foram construídas anteriormente.

## ✅ Solução Rápida

### Opção 1: Script Automatizado (Recomendado)

Execute o script que criei:

```bash
cd /caminho/para/mis-core
./rebuild-mis-energy.sh
```

Este script faz automaticamente:
1. Para os containers do MIS-Energy
2. Remove containers e imagens antigas
3. Limpa o cache do Docker
4. Reconstrói as imagens sem cache
5. Inicia os containers novos
6. Verifica logs e status

### Opção 2: Comandos Manuais

Se preferir fazer manualmente:

```bash
# 1. Ir para o diretório do projeto
cd /caminho/para/mis-core

# 2. Garantir que está no branch correto
git checkout mis-hub
git pull origin mis-hub

# 3. Parar os containers do MIS-Energy
docker-compose stop mis-energy-backend mis-energy-frontend mis-energy-collector

# 4. Remover containers antigos
docker-compose rm -f mis-energy-backend mis-energy-frontend mis-energy-collector

# 5. Remover imagens antigas (forçar rebuild)
docker rmi -f mis-core-mis-energy-backend:latest
docker rmi -f mis-core-mis-energy-frontend:latest
docker rmi -f mis-core-mis-energy-collector:latest

# 6. Limpar cache do Docker
docker builder prune -f

# 7. Reconstruir SEM CACHE (importante!)
docker-compose build --no-cache mis-energy-backend mis-energy-frontend mis-energy-collector

# 8. Iniciar os containers
docker-compose up -d mis-energy-backend mis-energy-frontend mis-energy-collector

# 9. Verificar status
docker-compose ps
docker-compose logs -f mis-energy-backend
```

## 🚨 Problemas Comuns

### 1. "As alterações ainda não aparecem"

**Causa:** Cache do navegador

**Solução:**
- Faça um **hard refresh** no navegador:
  - Chrome/Edge: `Ctrl+Shift+R` (Windows/Linux) ou `Cmd+Shift+R` (Mac)
  - Firefox: `Ctrl+F5` (Windows/Linux) ou `Cmd+Shift+R` (Mac)
- Ou limpe o cache do navegador completamente
- Ou abra em modo anônimo/privado

### 2. "Container não inicia / fica reiniciando"

**Causa:** Erro no código ou dependências faltando

**Solução:**
```bash
# Ver logs detalhados
docker-compose logs --tail=100 mis-energy-backend
docker-compose logs --tail=100 mis-energy-frontend

# Verificar se há erros de sintaxe Python
docker-compose exec mis-energy-backend python -m py_compile /app/src/routes/equipment.py
docker-compose exec mis-energy-backend python -m py_compile /app/src/routes/analytics_dashboard.py
```

### 3. "Erro de conexão com InfluxDB ou MySQL"

**Causa:** Serviços de infraestrutura não estão prontos

**Solução:**
```bash
# Verificar se InfluxDB está respondendo
docker-compose exec influxdb influx -execute 'SHOW DATABASES'

# Verificar se MySQL está respondendo
docker-compose exec mysql mysql -uroot -p${MYSQL_ROOT_PASSWORD} -e 'SHOW DATABASES'

# Se não estiverem, reinicie toda a stack
docker-compose restart
```

### 4. "Frontend mostra tela branca"

**Causa:** Erro de build do React ou variáveis de ambiente incorretas

**Solução:**
```bash
# Ver logs do frontend
docker-compose logs mis-energy-frontend

# Verificar se o build foi concluído
docker-compose exec mis-energy-frontend ls -la /usr/share/nginx/html

# Verificar variáveis de ambiente
docker-compose exec mis-energy-frontend env | grep VITE
```

### 5. "API retorna 500 Internal Server Error"

**Causa:** Erro no código Python do backend

**Solução:**
```bash
# Ver logs detalhados do backend
docker-compose logs --tail=200 mis-energy-backend

# Entrar no container e testar manualmente
docker-compose exec mis-energy-backend bash
cd /app
python -c "from src.routes.equipment import equipment_bp; print('OK')"
```

## 📋 Checklist de Validação

Após o rebuild, verifique se as seguintes funcionalidades estão funcionando:

### Backend
- [ ] Rota `/api/equipments/<id>/metrics` retorna métricas corretas por tipo
- [ ] Equipamentos de produção retornam: `flow_rate`, `total_production`, `efficiency`, `specific_consumption`
- [ ] Equipamentos de energia retornam: `power_kw`, `energy_kwh`, `demand_kw`, `power_factor`
- [ ] Rota `/api/analytics/dashboard-summary` retorna dados reais do InfluxDB
- [ ] Filtro `hierarchy_id` funciona corretamente

### Frontend
- [ ] Cards de equipamentos mostram métricas financeiras (custo/hora)
- [ ] Cards de produção mostram métricas de produção (não de energia)
- [ ] Dashboard principal mostra: Energia Total, Custo Total, Demanda de Pico, Fator de Potência
- [ ] Painel de métricas se adapta ao tipo de medidor
- [ ] Cores seguem padrão ISA-101 (verde, amarelo, vermelho)

## 🔧 Comandos Úteis

### Ver logs em tempo real
```bash
docker-compose logs -f mis-energy-backend
docker-compose logs -f mis-energy-frontend
```

### Entrar no container para debug
```bash
docker-compose exec mis-energy-backend bash
docker-compose exec mis-energy-frontend sh
```

### Reiniciar apenas um serviço
```bash
docker-compose restart mis-energy-backend
docker-compose restart mis-energy-frontend
```

### Verificar uso de recursos
```bash
docker stats mis-energy-backend mis-energy-frontend
```

### Limpar tudo e começar do zero
```bash
docker-compose down
docker system prune -a --volumes -f
docker-compose up -d --build
```

## 📞 Quando Pedir Ajuda

Se após seguir este guia as alterações ainda não aparecerem, forneça as seguintes informações:

1. **Logs do backend:**
   ```bash
   docker-compose logs --tail=100 mis-energy-backend > backend-logs.txt
   ```

2. **Logs do frontend:**
   ```bash
   docker-compose logs --tail=100 mis-energy-frontend > frontend-logs.txt
   ```

3. **Status dos containers:**
   ```bash
   docker-compose ps > containers-status.txt
   ```

4. **Commit atual:**
   ```bash
   git log -1 --oneline > current-commit.txt
   ```

5. **Resposta de uma rota da API:**
   ```bash
   curl http://localhost:5005/api/equipments/1/metrics > api-response.txt
   ```

## 🎓 Entendendo o Problema

### Por que isso acontece?

O Docker usa um sistema de **camadas (layers)** para construir imagens. Quando você faz `docker-compose up`:

1. O Docker verifica se já existe uma imagem com o nome especificado
2. Se existir, ele usa essa imagem (mesmo que o código-fonte tenha mudado)
3. Ele **não** verifica se o código-fonte foi atualizado

### Como o `--no-cache` resolve?

A flag `--no-cache` força o Docker a:
1. Ignorar todas as camadas em cache
2. Reconstruir a imagem do zero
3. Copiar novamente todos os arquivos do código-fonte
4. Reinstalar todas as dependências

### Por que não usar `--no-cache` sempre?

Porque é mais lento! O cache acelera muito o processo de build. Use `--no-cache` apenas quando:
- Fizer alterações significativas no código
- Atualizar dependências (requirements.txt, package.json)
- Tiver problemas que não consegue resolver

## 📚 Referências

- [Docker Compose Build Documentation](https://docs.docker.com/compose/reference/build/)
- [Docker Cache Best Practices](https://docs.docker.com/build/cache/)
- Commit com as alterações: `5aa21dca`
- Documentação das melhorias: `/home/ubuntu/resumo_melhorias_mis_energy.md`
