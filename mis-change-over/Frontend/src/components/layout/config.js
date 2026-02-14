// src/config.js

const config = {
  // Configurações da API para o Sidebar (linhas de produção)
  sidebarApi: {
    // URL base da API para linhas disponíveis
    // Exemplo: 'http://192.168.112.128:8000/api'
    // Para ambiente de produção, você pode usar uma variável de ambiente: process.env.REACT_APP_SIDEBAR_API_BASE_URL
    baseUrl: 'http://localhost:8000/api',
  },

  // Configurações da API para o MachineChat (LLM e dados da máquina)
  machineChatApi: {
    // Endpoint do LLM (LM Studio)
    // Exemplo: 'http://192.168.112.1:8080'
    // Para ambiente de produção, você pode usar uma variável de ambiente: process.env.REACT_APP_LLM_ENDPOINT
    llamaEndpoint: 'http://localhost:8080',

    // Endpoint da API de Dados (Flask)
    // Exemplo: 'http://127.0.0.1:5002/api'
    // Para ambiente de produção, você pode usar uma variável de ambiente: process.env.REACT_APP_DATA_API_ENDPOINT
    dataApiEndpoint: 'http://127.0.0.1:5002/api',
  },

  // Outras configurações globais (opcional)
  appSettings: {
    aiName: "LIIA", // Nome da IA
    defaultLine: "L01", // Linha padrão se nenhuma for selecionada
    speechRecognitionSupported: 'webkitSpeechRecognition' in window, // Verifica suporte a reconhecimento de voz
  }
};

export default config;