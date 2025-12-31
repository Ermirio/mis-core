# Instruções de Uso - Aplicação de Predição Genérica

## 🚀 Como Iniciar a Aplicação

### Pré-requisitos
- Python 3.11+
- Node.js 20+
- pnpm

### 1. Iniciar o Backend
```bash
cd /home/ubuntu/prediction_app_improved
pip3 install flask flask-cors sqlalchemy scikit-learn python-dotenv
python3 app.py
```
O backend estará disponível em: `http://localhost:5001`

### 2. Iniciar o Frontend
```bash
cd /home/ubuntu/prediction_app_improved/prediction-app-frontend
pnpm install
pnpm run dev
```
O frontend estará disponível em: `http://localhost:5173`

## 📋 Fluxo de Uso da Aplicação

### Passo 1: Gerenciar Linhas de Produção
1. Acesse a aba **"Linhas"**
2. Clique em **"Nova Linha"**
3. Preencha:
   - **Nome**: Ex: L01, L02, Linha A
   - **Descrição**: Descrição da linha de produção
4. Clique em **"Criar Linha"**

### Passo 2: Definir Targets de Predição
1. Acesse a aba **"Targets"**
2. Clique em **"Novo Target"**
3. Preencha:
   - **Nome**: Ex: Densidade, Temperatura, Pressão
   - **Unidade**: Ex: g/cm³, °C, bar, %
   - **Descrição**: O que será predito
4. Clique em **"Criar Target"**

### Passo 3: Criar e Configurar Modelos
1. Acesse a aba **"Modelos"**
2. Clique em **"Novo Modelo"** ou **"Criar Primeiro Modelo"**
3. Preencha:
   - **Nome**: Ex: RandomForest_v1, Modelo_Otimizado
   - **Tipo**: Selecione Random Forest ou Regressão Linear
4. Clique em **"Parâmetros do Modelo"** para configurar:

#### Para Random Forest:
- **Número de Árvores**: Quantidade de árvores (padrão: 100)
- **Profundidade Máxima**: Profundidade máxima das árvores (padrão: 10)
- **Seed Aleatória**: Semente para reprodutibilidade (padrão: 42)

#### Para Regressão Linear:
- Parâmetros específicos do modelo linear

5. Clique em **"Criar Modelo"**

### Passo 4: Coletar Dados
1. Acesse a aba **"Dados"**
2. Escolha o método de coleta:

#### Dados Manuais:
- Insira dados diretamente na interface
- Adicione amostras com valores de entrada e saída

#### Dados OPC:
- Configure a conexão OPC na aba **"OPC"**
- Defina as variáveis OPC para coleta automática
- Configure a variável target OPC

### Passo 5: Treinar o Modelo
1. Com dados coletados, acesse **"Modelos"**
2. Selecione o modelo desejado
3. Inicie o treinamento
4. Acompanhe o progresso no dashboard

### Passo 6: Fazer Predições
1. Acesse a aba **"Predição"**
2. Selecione:
   - **Linha**: Linha de produção
   - **Target**: O que predizer
   - **Modelo**: Modelo treinado
3. Clique em **"Fazer Predição"**
4. Visualize os resultados

## 🎛️ Interface da Aplicação

### Dashboard
- **Visão Geral**: Status completo do sistema
- **Linha Selecionada**: Linha ativa atual
- **Target Ativo**: Variável sendo predita
- **Modelo Ativo**: Modelo em uso
- **Status OPC**: Conexão com servidor OPC
- **Última Predição**: Resultado mais recente
- **Status do Modelo**: Informações de treinamento

### Navegação
- **Dashboard**: Visão geral do sistema
- **Linhas**: Gerenciar linhas de produção
- **Targets**: Definir variáveis de predição
- **Modelos**: Criar e configurar modelos ML
- **Dados**: Coletar dados para treinamento
- **Predição**: Executar predições
- **OPC**: Configurar conexão OPC UA

## ⚙️ Configurações Avançadas

### Configuração OPC
1. Acesse a aba **"OPC"**
2. Configure:
   - **URL do Servidor**: Endereço do servidor OPC UA
   - **Variáveis de Entrada**: Tags OPC para features
   - **Variável Target**: Tag OPC para a variável a ser predita
3. Teste a conexão

### Parâmetros de Modelos
- **Random Forest**:
  - `n_estimators`: Número de árvores (mais árvores = maior precisão, mais lento)
  - `max_depth`: Profundidade máxima (controla overfitting)
  - `random_state`: Seed para reprodutibilidade

- **Regressão Linear**:
  - Parâmetros de regularização
  - Configurações de solver

## 🔧 Solução de Problemas

### Backend não inicia
- Verifique se todas as dependências estão instaladas
- Confirme se a porta 5001 está disponível
- Verifique logs de erro no terminal

### Frontend não carrega
- Execute `pnpm install` para instalar dependências
- Verifique se a porta 5173 está disponível
- Confirme se o backend está rodando

### Erro de conexão OPC
- Verifique se o servidor OPC UA está ativo
- Confirme a URL e credenciais
- Teste conectividade de rede

### Modelo não treina
- Verifique se há dados suficientes coletados
- Confirme se o target está definido corretamente
- Verifique logs de erro no backend

## 📊 Monitoramento

### Métricas Importantes
- **Status do Modelo**: Treinado/Não Treinado
- **Número de Amostras**: Quantidade de dados coletados
- **Precisão do Modelo**: Métricas de performance
- **Status OPC**: Conectado/Desconectado

### Logs
- Backend: Logs no terminal do Flask
- Frontend: Console do navegador (F12)
- Banco de Dados: Arquivo SQLite local

## 🚀 Próximos Passos

1. **Coleta de Dados**: Comece coletando dados históricos
2. **Treinamento**: Treine modelos com diferentes parâmetros
3. **Validação**: Teste predições com dados conhecidos
4. **Produção**: Implemente em ambiente produtivo
5. **Monitoramento**: Acompanhe performance dos modelos

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs de erro
2. Consulte a documentação técnica
3. Teste com dados de exemplo
4. Valide configurações de rede e OPC

---

**Aplicação de Predição Genérica** - Versão 2.0
*Transformando dados em insights preditivos*

