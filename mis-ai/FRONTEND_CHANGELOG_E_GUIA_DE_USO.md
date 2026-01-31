# Changelog e Guia de Uso - Frontend

## 1. Resumo das Alterações

O frontend foi atualizado para incorporar as novas funcionalidades de **Treinamento Automático** e **Controle Preditivo**, com foco em uma interface de alta qualidade seguindo os padrões **ISA-101** e **ISA-88**.

### Novas Páginas

- **Controle Preditivo**: Uma nova página dedicada ao monitoramento e aplicação de recomendações de ajuste preditivo.
- **Treinamento Automático**: Uma nova página para visualizar o status da sincronização automática de variáveis de referência e os dados capturados.

### Alterações em Páginas Existentes

- **Configuração OPC**: O formulário de criação e edição de variáveis foi atualizado para suportar os novos tipos `reference` e `control`, com campos condicionais para suas respectivas configurações.
- **Sidebar**: Adicionados novos links para as páginas de Controle Preditivo e Treinamento Automático.

## 2. Guia de Uso

### 2.1. Configurando Variáveis de Referência e Controle

1. Navegue até a página **Configuração OPC**.
2. Clique em **Nova Variável** ou edite uma existente.
3. No campo **Categoria da Variável**, selecione:
    - **Referência (Treinamento Auto)**: Para configurar uma variável que irá capturar dados automaticamente para treinar um modelo.
        - **Target Associado**: Selecione o target que será treinado com os dados desta variável.
    - **Controle (Ajuste Preditivo)**: Para configurar uma variável que receberá recomendações de ajuste.
        - **Lógica de Controle**: Defina se a lógica é direta ou reversa.
        - **Fator de Relação**: Defina a intensidade do ajuste (0 a 100%).
        - **Ajuste Mínimo/Máximo**: Defina limites de segurança para o ajuste.

### 2.2. Controle Preditivo

1. Navegue até a página **Controle Preditivo**.
2. Selecione a linha desejada no header.
3. A página exibirá as recomendações de ajuste pendentes, com as seguintes informações:
    - Variável de Controle
    - Predição, Alvo e Erro
    - Valor Atual, Ajuste Sugerido e Novo Valor
4. Para aplicar um ajuste, clique em **Aplicar** e confirme na caixa de diálogo.
5. Para visualizar o histórico de recomendações, clique em **Histórico**.

### 2.3. Treinamento Automático

1. Navegue até a página **Treinamento Automático**.
2. Selecione a linha desejada no header.
3. A página exibirá o status da sincronização automática, incluindo:
    - Status do Sync (Ativo/Inativo)
    - Número de variáveis de referência configuradas
    - Quantidade de dados capturados
    - Hora da última captura
4. A tabela de **Dados Capturados Automaticamente** exibirá os últimos 100 registros gerados.

## 3. Próximos Passos

Com o frontend e backend implementados, o sistema está pronto para ser utilizado. Recomenda-se agora realizar testes em um ambiente de homologação para validar o fluxo completo com dados reais do processo.
