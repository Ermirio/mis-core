// src/config.js

/**
 * @file Arquivo de configuração centralizado para o frontend React.
 * @description Este arquivo define todas as URLs de API, configurações da IA, e
 * outros parâmetros globais do aplicativo React.
 * Utilizar este arquivo garante consistência e facilita a manutenção
 * e a adaptação para diferentes ambientes (desenvolvimento, produção).
 */

const config = {
  // Configurações da API para o componente Sidebar (linhas de produção).
  // Esta URL é usada para buscar as linhas de produção disponíveis.
  sidebarApi: {
    // URL base da API Django para linhas disponíveis.
    // Em ambiente de produção, esta URL pode vir de uma variável de ambiente do React,
    // por exemplo: process.env.REACT_APP_SIDEBAR_API_BASE_URL.
    baseUrl: 'http://localhost:8000/api', // Exemplo: API Django
  },

  // Configurações da API para o componente MachineChat (LLM e dados da máquina).
  // Estas URLs são usadas para comunicação com o LLM (LM Studio) e a API de dados Flask.
  machineChatApi: {
    // Endpoint do LLM (Large Language Model), como o LM Studio.
    // Lembre-se de substituir 'MODEL_ID_DO_SEU_LM_STUDIO' no MachineChat.js pelo ID real do modelo.
    // Em produção, esta URL pode ser carregada de uma variável de ambiente.
    llamaEndpoint: 'http://localhost.1:8080', // Exemplo: LM Studio
    // Tempo limite (em milissegundos) para a requisição ao LLM.
    llamaTimeout: 540000, // 9 minutos, para respostas mais longas da IA.

    // Endpoint da API de Dados (Flask).
    // Esta API fornece dados de máquinas em tempo real ou históricos.
    // Em produção, esta URL pode ser carregada de uma variável de ambiente.
    dataApiEndpoint: 'http://localhost:5002/api', // Exemplo: API Flask
    // Tempo limite (em milissegundos) para as requisições à API de Dados.
    dataApiTimeout: 20000, // 20 segundos.
  },

  // Configurações específicas para o componente TrocaAutomaticaContent.
  // Essas configurações controlam a interação com a API de troca de SKUs e o histórico.
  trocaAutomatica: {
    // URL base da API Django para sincronização e troca de SKUs.
    // Esta pode ser a mesma do `sidebarApi` se for o mesmo backend, ou uma específica.
    baseUrl: 'http://localhost:8000/api', // Ajuste para a URL correta da sua API de troca
    // Endpoint para sincronizar SKUs.
    syncSkusEndpoint: '/sincronizar-skus/',
    // Endpoint para histórico de trocas.
    historicoTrocasEndpoint: '/api/linha/{line}', // '{line}' é um placeholder
    // Endpoint para realizar a troca de SKU.
    trocarSkuEndpoint: '/trocar_sku/',

    // Intervalo (em milissegundos) para verificar o status de conexão da API Django.
    djangoHealthCheckInterval: 30000, // 30 segundos.
    // Tempo limite (em milissegundos) para a requisição de saúde do Django.
    djangoHealthCheckTimeout: 15000, // 15 segundos.

    // Tamanho padrão da página para o histórico de trocas.
    defaultPageSize: 10,
    // Atraso (em milissegundos) para recarregar o histórico após uma troca bem-sucedida.
    // Dá tempo para o backend processar e registrar a troca.
    postTrocaReloadDelay: 1000, // 1 segundo.
  },

  // Outras configurações globais do aplicativo React.
  appSettings: {
    aiName: "LIIA", // Nome do assistente de IA.
    defaultLine: "L01", // Linha padrão selecionada ao iniciar o aplicativo.
    // Verifica se o navegador suporta reconhecimento de voz.
    speechRecognitionSupported: 'webkitSpeechRecognition' in window,
    // Duração padrão (em milissegundos) para os toasts (notificações pop-up).
    toastDuration: 5000, // 5 segundos.
  },
};

export default config;