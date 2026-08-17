// src/config.js
// Todas as URLs são lidas de variáveis de ambiente (.env / .env.production)
// para evitar hardcode e garantir funcionamento atrás do proxy reverso OT.

const config = {
  sidebarApi: {
    // Em produção: /mis-change-over-api  (proxiado pelo nginx OT)
    // Em dev: http://localhost:8000/api
    baseUrl: process.env.REACT_APP_SIDEBAR_API_BASE_URL || '/api',
  },

  machineChatApi: {
    llamaEndpoint:   process.env.REACT_APP_LLAMA_ENDPOINT    || '/',
    dataApiEndpoint: process.env.REACT_APP_DATA_API_ENDPOINT || '/mis-change-over-data-api',
  },

  appSettings: {
    aiName:          process.env.REACT_APP_AI_NAME      || 'LIIA',
    defaultLine:     process.env.REACT_APP_DEFAULT_LINE || 'L01',
    speechRecognitionSupported: 'webkitSpeechRecognition' in window,
  },
};

export default config;