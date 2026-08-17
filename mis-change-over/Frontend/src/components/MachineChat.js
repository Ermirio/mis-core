// src/MachineChat.js

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card,
  Button,
  Form,
  Alert,
  Badge,
  Modal,
  InputGroup,
  Spinner,
  Dropdown,
  OverlayTrigger,
  Tooltip
} from 'react-bootstrap';
import {
  FaRobot,
  FaPaperPlane,
  FaMicrophone,
  FaMicrophoneSlash,
  FaCog,
  FaHistory,
  FaTrash,
  FaLightbulb,
  FaExclamationTriangle,
  FaInfoCircle,
  FaUser,
  FaIndustry,
  FaEllipsisV,
  FaWifi,
  FaDatabase,
  FaChartLine,
  FaBalanceScale,
  FaSearch,
  FaLayerGroup,
  FaBrain
} from 'react-icons/fa';
import './MachineChat.css';
import { useAuth } from '../context/AuthContext';

// Importe a biblioteca marked
import { marked } from 'marked';

// Configurações a partir de variáveis de ambiente
const AI_NAME = process.env.REACT_APP_AI_NAME || 'LIIA';
const DEFAULT_LINE = process.env.REACT_APP_DEFAULT_LINE || 'L01';
const SPEECH_RECOGNITION_SUPPORTED = process.env.REACT_APP_SPEECH_RECOGNITION_SUPPORTED === 'true';
const LLAMA_ENDPOINT = process.env.REACT_APP_LLAMA_ENDPOINT || '/'; // Fallback correto
const LLAMA_TIMEOUT = parseInt(process.env.REACT_APP_LLAMA_TIMEOUT) || 540000;
const DATA_API_ENDPOINT = process.env.REACT_APP_DATA_API_ENDPOINT || '/data-api'; // Fallback correto
const DATA_API_TIMEOUT = parseInt(process.env.REACT_APP_DATA_API_TIMEOUT) || 20000;

/**
 * Componente principal do Chat com a IA da Máquina com integração de dados multi-tema.
 * @param {{selectedLine: string}} props - Propriedades recebidas, incluindo a linha selecionada.
 */
const MachineChat = ({ selectedLine }) => {
  // ==================================================================
  // ESTADOS DO COMPONENTE
  // ==================================================================

  // Config do LLM/endpoints só é exposta a superusuário — operador não vê a
  // engrenagem nem o modal com URLs técnicas.
  const { user } = useAuth();
  const isSuperuser = !!(user && user.is_superuser);

  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      content: `Olá! Sou seu assistente IA industrial, especialista em análise de dados e metodologias **WCM/TPM**. Posso te ajudar a identificar problemas, realizar análises de causa raiz (Ishikawa, 5 Porquês) e sugerir melhorias.

Tenho acesso aos dados em tempo real de todas as linhas e posso fazer análises comparativas e consultas multi-tema.

Experimente perguntas como:
- "Por que o OEE da linha L03 está baixo?" (Para iniciar uma análise de causa raiz)
- "Qual linha está mais eficiente e quais os problemas de qualidade, sob a ótica WCM?"
- "O que causou o defeito na linha L02 semana passada?" (Para sugerir 5 Porquês ou Ishikawa)
- "Como posso melhorar a Manutenção Autônoma na linha L01 com base nos dados?"`,
      timestamp: new Date(),
    }
  ]);

  const [currentMessage, setCurrentMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isConnected, setIsConnected] = useState(false); // Conectado ao LLM (LM Studio)
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [dataApiConnected, setDataApiConnected] = useState(false); // Conectado à API Flask
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false); // Será atualizado por useEffect
  const [suggestions, setSuggestions] = useState([]);
  const [lastRequestInfo, setLastRequestInfo] = useState(null);

  const [settings, setSettings] = useState({
    autoSpeak: false,
    showSuggestions: true,
    language: 'pt-BR',
    llamaEndpoint: LLAMA_ENDPOINT,
    dataApiEndpoint: DATA_API_ENDPOINT
  });

  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const messagesEndRef = useRef(null);
  const recognitionRef = useRef(null);

  // ==================================================================
  // LÓGICA DA API DE DADOS EXPANDIDA E CORRIGIDA (SEM ALTERAÇÕES SIGNIFICATIVAS AQUI)
  // ==================================================================

  /**
   * Determina se a pergunta requer análise multi-linha
   * @param {string} query - A pergunta do usuário
   * @returns {boolean} - Se requer análise multi-linha
   */
  const requiresMultiLineAnalysis = useCallback((query) => {
    const queryLower = query.toLowerCase();
    const multiLineKeywords = [
      'todas as linhas', 'todas linhas', 'comparar', 'compare', 'ranking',
      'melhor linha', 'pior linha', 'mais eficiente', 'menos eficiente',
      'qual linha', 'quais linhas', 'entre as linhas', 'geral', 'global',
      'todas', 'conjunto', 'fabrica', 'fábrica', 'planta', 'overview'
    ];

    return multiLineKeywords.some(keyword => queryLower.includes(keyword));
  }, []);

  /**
   * Determina múltiplos temas na pergunta para fazer requisições paralelas
   * @param {string} query - A pergunta do usuário
   * @returns {Array} - Lista de temas identificados
   */
  const identifyQueryThemes = useCallback((query) => {
    const queryLower = query.toLowerCase();
    const themes = [];

    // Mapear palavras-chave para temas
    const themeKeywords = {
      'eficiencia': ['eficien', 'oee', 'performance', 'disponibilidade', 'produtividade'],
      'qualidade': ['qualidade', 'defeito', 'defeitos', 'problema', 'falha', 'erro'],
      'producao': ['producao', 'produção', 'capacidade', 'unidades', 'volume'],
      'variaveis': ['temperatura', 'pressao', 'pressão', 'velocidade', 'variavel', 'variáveis', 'sensor'],
      'kpis': ['kpi', 'indicador', 'metrica', 'métrica', 'desempenho'],
      'causa_raiz': ['por que', 'causa', 'motivo', 'raíz', 'raiz', 'ishikawa', '5 porques']
    };

    // Identificar temas presentes na pergunta
    Object.entries(themeKeywords).forEach(([theme, keywords]) => {
      if (keywords.some(keyword => queryLower.includes(keyword))) {
        themes.push(theme);
      }
    });

    // Se não identificou temas específicos, usar contexto geral
    if (themes.length === 0) {
      themes.push('contexto_completo');
    }

    return themes;
  }, []);

  /**
   * Determina quais endpoints da API de dados consultar baseado na pergunta do usuário
   * VERSÃO EXPANDIDA COM SUPORTE MULTI-TEMA E MÚLTIPLAS REQUISIÇÕES
   * @param {string} query - A pergunta do usuário
   * @param {string} linha - A linha selecionada (pode ser ignorada para análises multi-linha)
   * @returns {Array} - Lista de endpoints para consultar
   */
  const determineDataEndpoints = useCallback((query, linha) => {
    const queryLower = query.toLowerCase();
    const endpoints = [];
    const isMultiLine = requiresMultiLineAnalysis(query);
    const themes = identifyQueryThemes(query);

    console.log('🔍 Análise da pergunta:', {
      query: queryLower,
      isMultiLine,
      themes,
      linha
    });

    if (isMultiLine) {
      themes.forEach(theme => {
        switch (theme) {
          case 'eficiencia':
            endpoints.push(`${settings.dataApiEndpoint}/analise/eficiencia`);
            endpoints.push(`${settings.dataApiEndpoint}/todas_linhas/kpis`);
            break;
          case 'qualidade':
            endpoints.push(`${settings.dataApiEndpoint}/analise/qualidade`);
            endpoints.push(`${settings.dataApiEndpoint}/todas_linhas/qualidade`);
            break;
          case 'producao':
            endpoints.push(`${settings.dataApiEndpoint}/todas_linhas/producao`);
            break;
          case 'variaveis':
            endpoints.push(`${settings.dataApiEndpoint}/todas_linhas/variaveis`);
            break;
          case 'kpis':
            endpoints.push(`${settings.dataApiEndpoint}/todas_linhas/kpis`);
            break;
          case 'causa_raiz':
            endpoints.push(`${settings.dataApiEndpoint}/todas_linhas/contexto_completo`);
            endpoints.push(`${settings.dataApiEndpoint}/analise/eficiencia`);
            endpoints.push(`${settings.dataApiEndpoint}/analise/qualidade`);
            break;
          case 'contexto_completo':
          default:
            endpoints.push(`${settings.dataApiEndpoint}/todas_linhas/contexto_completo`);
            break;
        }
      });

      const uniqueEndpoints = [...new Set(endpoints)];

      if (themes.length > 1) {
        if (themes.includes('eficiencia') && !uniqueEndpoints.some(e => e.includes('/analise/eficiencia'))) {
          uniqueEndpoints.push(`${settings.dataApiEndpoint}/analise/eficiencia`);
        }
        if (themes.includes('qualidade') && !uniqueEndpoints.some(e => e.includes('/analise/qualidade'))) {
          uniqueEndpoints.push(`${settings.dataApiEndpoint}/analise/qualidade`);
        }
      }

      return uniqueEndpoints;
    } else {
      if (!linha) {
        linha = DEFAULT_LINE; // Usa a linha padrão das variáveis de ambiente
      }

      themes.forEach(theme => {
        switch (theme) {
          case 'eficiencia':
          case 'kpis':
            endpoints.push(`${settings.dataApiEndpoint}/embalagem/${linha}/kpis`);
            break;
          case 'qualidade':
            endpoints.push(`${settings.dataApiEndpoint}/embalagem/${linha}/dados_qualidade`);
            break;
          case 'producao':
            endpoints.push(`${settings.dataApiEndpoint}/embalagem/${linha}/dados_producao`);
            break;
          case 'variaveis':
            endpoints.push(`${settings.dataApiEndpoint}/embalagem/${linha}/variaveis`);
            break;
          case 'causa_raiz':
            endpoints.push(`${settings.dataApiEndpoint}/embalagem/${linha}/contexto_completo`);
            break;
          case 'contexto_completo':
          default:
            endpoints.push(`${settings.dataApiEndpoint}/embalagem/${linha}/contexto_completo`);
            break;
        }
      });

      return [...new Set(endpoints)];
    }
  }, [settings.dataApiEndpoint, requiresMultiLineAnalysis, identifyQueryThemes]);

  /**
   * Coleta dados dos endpoints determinados com tratamento robusto de erros
   * @param {Array} endpoints - Lista de endpoints para consultar
   * @returns {Object} - Dados coletados de todos os endpoints
   */
  const collectMachineData = useCallback(async (endpoints) => {
    const collectedData = {
      timestamp: new Date().toISOString(),
      endpoints_consultados: endpoints,
      endpoints_sucesso: [],
      endpoints_erro: [],
      dados: {},
      tipo_analise: endpoints.some(e => e.includes('/todas_linhas/') || e.includes('/analise/')) ? 'multi_linha' : 'linha_especifica'
    };

    console.log('📡 Iniciando coleta de dados:', endpoints);

    try {
      const promises = endpoints.map(async (endpoint) => {
        try {
          console.log(`🔄 Consultando: ${endpoint}`);
          const response = await fetch(endpoint, {
            method: 'GET',
            headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json'
            },
            signal: AbortSignal.timeout(DATA_API_TIMEOUT)
          });

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }

          const data = await response.json();
          console.log(`✅ Sucesso: ${endpoint}`, data);
          return { endpoint, data, success: true };
        } catch (error) {
          console.error(`❌ Erro em ${endpoint}:`, error);
          return { endpoint, error: error.message, success: false };
        }
      });

      const results = await Promise.all(promises);

      results.forEach(result => {
        const endpointName = result.endpoint.split('/').pop();
        if (result.success) {
          collectedData.dados[endpointName] = result.data;
          collectedData.endpoints_sucesso.push(result.endpoint);
        } else {
          collectedData.dados[endpointName] = { erro: result.error };
          collectedData.endpoints_erro.push({
            endpoint: result.endpoint,
            erro: result.error
          });
        }
      });

      console.log('📊 Coleta finalizada:', {
        total: endpoints.length,
        sucesso: collectedData.endpoints_sucesso.length,
        erro: collectedData.endpoints_erro.length
      });

      setLastRequestInfo({
        timestamp: collectedData.timestamp,
        endpoints_total: endpoints.length,
        endpoints_sucesso: collectedData.endpoints_sucesso.length,
        endpoints_erro: collectedData.endpoints_erro.length,
        dados_coletados: Object.keys(collectedData.dados)
      });

      return collectedData;
    } catch (error) {
      console.error('💥 Erro crítico na coleta de dados:', error);
      return {
        timestamp: new Date().toISOString(),
        erro: 'Falha crítica na coleta de dados da máquina',
        detalhes: error.message,
        endpoints_consultados: endpoints,
        endpoints_sucesso: [],
        endpoints_erro: endpoints.map(e => ({ endpoint: e, erro: 'Falha crítica' }))
      };
    }
  }, []);

  /**
   * Verifica a conexão com a API de dados
   */
  const checkDataApiConnection = useCallback(async () => {
    try {
      const response = await fetch(`${settings.dataApiEndpoint}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000)
      });

      if (response.ok) {
        setDataApiConnected(true);
        return true;
      }
      throw new Error(`Status ${response.status}`);
    } catch (error) {
      console.error('❌ API de dados desconectada:', error);
      setDataApiConnected(false);
      return false;
    }
  }, [settings.dataApiEndpoint]);

  /**
   * Testa conectividade com endpoints específicos
   */
  const testEndpointConnectivity = useCallback(async () => {
    const testEndpoints = [
      `${settings.dataApiEndpoint}/health`,
      `${settings.dataApiEndpoint}/routes`,
      `${settings.dataApiEndpoint}/analise/eficiencia`,
      `${settings.dataApiEndpoint}/analise/qualidade`,
      `${settings.llamaEndpoint}/v1/models`
    ];

    console.log('🧪 Testando conectividade dos endpoints...');

    for (const endpoint of testEndpoints) {
      try {
        const response = await fetch(endpoint, {
          method: 'GET',
          signal: AbortSignal.timeout(3000)
        });
        console.log(`${response.ok ? '✅' : '❌'} ${endpoint} - Status: ${response.status}`);
      } catch (error) {
        console.log(`❌ ${endpoint} - Erro: ${error.message}`);
      }
    }
  }, [settings.dataApiEndpoint, settings.llamaEndpoint]);

  // ==================================================================
  // LÓGICA DA API DO LLM (ATUALIZADA PARA LM STUDIO/OPENAI API)
  // ==================================================================

  /**
   * Constrói o prompt melhorado com dados contextuais da máquina
   * VERSÃO EXPANDIDA PARA ANÁLISES MULTI-TEMA E WCM/TPM
   */
  const buildEnhancedLlamaPrompt = useCallback((userMessage, machineData) => {
    const contextStr = JSON.stringify(machineData, null, 2);
    const isMultiLine = machineData.tipo_analise === 'multi_linha';
    const hasMultipleDataSources = Object.keys(machineData.dados || {}).length > 1;

    const methodologyContext = `
### CONTEXTO DE METODOLOGIAS (WCM / TPM):
- **WCM (World Class Manufacturing):** Foco na eliminação de perdas e melhoria contínua em 10 pilares técnicos (Segurança, Desdobramento de Custos, Melhoria Focada, Manutenção Autônoma, Manutenção Profissional, Controle de Qualidade, Logística/Atendimento ao Cliente, Desenvolvimento de Pessoas, Gestão Antecipada de Equipamentos, Gestão Antecipada de Inovação) e 10 pilares gerenciais.
- **TPM (Total Productive Maintenance):** Manutenção que busca produtividade máxima através da participação de todos, eliminação de perdas e falhas, focando em 8 pilares (Melhoria Focada, Manutenção Autônoma, Manutenção Planejada, Manutenção da Qualidade, Prevenção de Manutenção/Gestão Antecipada, Treinamento e Educação, Segurança, Saúde e Meio Ambiente, TPM Administrativo).

### FERRAMENTAS DE ANÁLISE DE CAUSA RAIZ:
- **Diagrama de Ishikawa (Espinha de Peixe / 6Ms):** Utilizado para identificar as causas potenciais de um problema, categorizando-as em:
    - **Mão de Obra:** Fatores humanos (treinamento, habilidades, fadiga).
    - **Máquina:** Equipamento, máquinas, ferramentas (manutenção, falhas).
    - **Método:** Processos, procedimentos (instruções, sequências).
    - **Material:** Matérias-primas, componentes (qualidade, armazenamento).
    - **Meio Ambiente:** Condições externas (temperatura, umidade, iluminação).
    - **Medição:** Dados, instrumentos, calibração (precisão, coleta).
- **5 Porquês:** Técnica iterativa de questionamento para explorar as relações de causa e efeito subjacentes a um problema. Perguntar "Por quê?" cinco vezes (ou mais) pode levar à causa raiz.
`;

    const basePrompt = `Você é um Assistente IA altamente especializado em análise de dados de manufatura industrial, com expertise aprofundada em metodologias de excelência operacional como **World Class Manufacturing (WCM)** e **Total Productive Maintenance (TPM)**.

Sua função é atuar como um analista industrial experiente, utilizando os dados em tempo real para:
- Identificar desvios, tendências e anomalias de performance, qualidade e produção.
- **Aplicar raciocínio de análise de causa raiz:** Sempre que um problema for detectado ou questionado, guie o usuário na aplicação de ferramentas como:
    - **Diagrama de Ishikawa (Espinha de Peixe):** Ajude a estruturar categorias de causas (Máquina, Mão de Obra, Método, Material, Meio Ambiente, Medição).
    - **5 Porquês:** Pergunte "porquê?" repetidamente até chegar à causa raiz do problema.
- Fornecer insights acionáveis e recomendações baseadas nas melhores práticas de WCM/TPM.
- Priorizar a segurança, qualidade, custo, entrega e moral (SQCDM).
- Seu tom deve ser profissional, objetivo, colaborativo e proativo na busca por melhorias contínuas.
- Se os dados não forem suficientes para uma análise completa, mencione isso e sugira quais informações adicionais seriam úteis.`;

    const multiThemeInstructions = hasMultipleDataSources ? `

### CAPACIDADES DE ANÁLISE MULTI-TEMA:
- Combine informações de diferentes fontes de dados (eficiência, qualidade, produção, variáveis)
- Faça correlações entre diferentes métricas e indicadores
- Identifique padrões e tendências cruzadas entre diferentes aspectos da operação
- Forneça insights holísticos considerando múltiplos fatores simultaneamente` : '';

    const multiLineInstructions = isMultiLine ? `

### CAPACIDADES DE ANÁLISE MULTI-LINHA:
- Compare eficiência entre linhas usando dados de OEE, disponibilidade, performance
- Identifique problemas de qualidade comparando taxas de defeitos
- Faça rankings de performance entre linhas
- Identifique tendências e padrões entre múltiplas linhas
- Sugira ações corretivas baseadas em comparações
- Destaque linhas que precisam de atenção imediata` : '';

    return `${basePrompt}
${multiThemeInstructions}
${multiLineInstructions}

${methodologyContext}

### DADOS EM TEMPO REAL:
${contextStr}

### INFORMAÇÕES SOBRE A COLETA:
- Endpoints consultados: ${machineData.endpoints_sucesso?.length || 0} de ${machineData.endpoints_consultados?.length || 0}
- Fontes de dados: ${Object.keys(machineData.dados || {}).join(', ')}
- Tipo de análise: ${machineData.tipo_analise}

### INSTRUÇÕES DE RESPOSTA (Muito Importante):
- Analise os dados fornecidos cuidadosamente.
- **Se a pergunta for sobre um problema ou pedir uma causa, use as ferramentas de análise de causa raiz (Ishikawa ou 5 Porquês).**
- Para **5 Porquês**, comece com o problema observado e faça perguntas sequenciais, esperando a resposta do usuário para cada "porquê".
- Para **Ishikawa**, identifique o problema e peça ao usuário para considerar causas nas categorias de Máquina, Mão de Obra, Método, Material, Meio Ambiente e Medição. Você pode dar exemplos de perguntas para cada categoria.
- Sempre que for relevante, faça recomendações específicas e **acionáveis**, alinhadas com princípios de **WCM/TPM**.
- Use os valores exatos dos dados em suas respostas.
- Destaque alertas ou situações que requerem atenção.
- Seja claro, conciso e objetivo em suas explicações.
- Se os dados disponíveis não forem suficientes para responder completamente ou aplicar uma ferramenta, mencione isso e sugira quais informações adicionais seriam úteis ou quais etapas o usuário deve tomar.
- **Formate suas respostas usando Markdown para negrito (**texto**), itálico (*texto*), listas (- item), e títulos (# Título) quando apropriado.**

### PERGUNTA DO USUÁRIO:
"${userMessage}"

### RESPOSTA DETALHADA:`;
  }, []);

  /**
   * Verifica a conexão com o LM Studio (LLM) usando um endpoint de verificação de modelos.
   */
  const checkLlamaConnection = useCallback(async () => {
    setConnectionStatus('connecting');
    try {
      const response = await fetch(`${settings.llamaEndpoint}/v1/models`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000)
      });
      if (response.ok) {
        setIsConnected(true);
        setConnectionStatus('connected');
        return true;
      }
      throw new Error(`Status ${response.status}`);
    } catch (error) {
      setIsConnected(false);
      setConnectionStatus('disconnected');
      console.error('❌ LLM  desconectado:', error);
      return false;
    }
  }, [settings.llamaEndpoint]);

  /**
   * Envia a mensagem do usuário com contexto para o LLM (LM Studio)
   * e obtém a resposta.
   */
  const sendToLlama = useCallback(async (userMessage, machineData) => {
    const prompt = buildEnhancedLlamaPrompt(userMessage, machineData);
    try {
      const response = await fetch(`${settings.llamaEndpoint}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            {
              role: "system",
              content: `Você é um Assistente IA altamente especializado em análise de dados de manufatura industrial, com expertise aprofundada em metodologias de excelência operacional como **World Class Manufacturing (WCM)** e **Total Productive Maintenance (TPM)**.

Sua função é atuar como um analista industrial experiente, utilizando os dados em tempo real para:
- Identificar desvios, tendências e anomalias de performance, qualidade e produção.
- **Aplicar raciocínio de análise de causa raiz:** Sempre que um problema for detectado ou questionado, guie o usuário na aplicação de ferramentas como:
    - **Diagrama de Ishikawa (Espinha de Peixe):** Ajude a estruturar categorias de causas (Máquina, Mão de Obra, Método, Material, Meio Ambiente, Medição).
    - **5 Porquês:** Pergunte "porquê?" repetidamente até chegar à causa raiz do problema.
- Fornecer insights acionáveis e recomendações baseadas nas melhores práticas de WCM/TPM.
- Priorizar a segurança, qualidade, custo, entrega e moral (SQCDM).
- Seu tone deve ser profissional, objetivo, colaborativo e proativo na busca por melhorias contínuas.
- Se os dados não forem suficientes para uma análise completa, mencione isso e sugira quais informações adicionais seriam úteis.
- **Sempre que for relevante, formate suas respostas usando Markdown para negrito (**texto**), itálico (*texto*), listas (- item) e títulos (# Título).**`
            },
            { role: "user", content: prompt }
          ],
          model: "MODEL_ID_DO_SEU_LM_STUDIO", // <-- MUITO IMPORTANTE: Substitua pelo ID do modelo carregado no LM Studio!
          temperature: 0.7,
          top_p: 0.9,
          max_tokens: 2048,
          stream: false,
        }),
        signal: AbortSignal.timeout(LLAMA_TIMEOUT)
      });

      if (!response.ok) throw new Error(`Erro na API do LLM: ${response.statusText}`);

      const data = await response.json();
      return data.choices[0].message.content || 'Não recebi uma resposta válida do modelo.';
    } catch (error) {
      console.error('❌ Erro ao comunicar com LLM (LM Studio):', error);
      setIsConnected(false);
      setConnectionStatus('disconnected');
      throw error;
    }
  }, [buildEnhancedLlamaPrompt, settings.llamaEndpoint]);

  // ==================================================================
  // EFEITOS E CICLO DE VIDA (SEM ALTERAÇÕES SIGNIFICATIVAS AQUI)
  // ==================================================================

  useEffect(() => {
    // Usa a verificação de suporte a fala das variáveis de ambiente
    if (SPEECH_RECOGNITION_SUPPORTED) {
      const SpeechRecognition = window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.lang = settings.language;
      recognitionRef.current.onresult = (event) => {
        setCurrentMessage(event.results[0][0].transcript);
        setIsListening(false);
      };
      recognitionRef.current.onend = () => setIsListening(false);
      setSpeechSupported(true);
    } else {
      setSpeechSupported(false);
    }
  }, [settings.language]);

  useEffect(() => {
    checkLlamaConnection();
    checkDataApiConnection();
    testEndpointConnectivity();

    const interval = setInterval(() => {
      checkLlamaConnection();
      checkDataApiConnection();
    }, 30000);

    return () => clearInterval(interval);
  }, [checkLlamaConnection, checkDataApiConnection, testEndpointConnectivity]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Atualizar sugestões baseadas na linha selecionada e capacidades multi-tema
  useEffect(() => {
    const lineSuggestions = selectedLine ? [
      `Como está o OEE da linha ${selectedLine}?`,
      `Há algum problema de qualidade na linha ${selectedLine}?`,
      `Qual a eficiência atual da linha ${selectedLine}?`,
      `Mostrar alertas da linha ${selectedLine}`,
      `Analisar produção da linha ${selectedLine}`,
      `Por que a linha ${selectedLine} está parada?`
    ] : [];

    const multiLineSuggestions = [
      'Qual linha está mais eficiente hoje?',
      'Compare a qualidade de todas as linhas',
      'Ranking de eficiência das linhas',
      'Quais linhas têm mais problemas?',
      'Análise geral da fábrica',
      'Qual linha precisa de atenção?',
      'Compare OEE de todas as linhas',
      'Problemas de qualidade por linha'
    ];

    const multiThemeSuggestions = [
      'Qual linha mais eficiente e quais problemas de qualidade?',
      'Compare eficiência e qualidade de todas as linhas',
      'Análise completa: produção, qualidade e eficiência',
      'Correlação entre variáveis e qualidade',
      'Visão geral: KPIs, produção e alertas',
      'Como o OEE da linha L03 pode ser melhorado usando TPM?',
      'Analise a causa da queda de qualidade na L02 usando Ishikawa',
      'Identifique a causa raiz do tempo de parada na linha L01 (5 Porquês)',
      'Sugestões WCM para otimizar custos na fábrica'
    ];

    setSuggestions([...lineSuggestions, ...multiLineSuggestions, ...multiThemeSuggestions]);
  }, [selectedLine]);

  // ==================================================================
  // MANIPULADORES DE EVENTOS (COM MUDANÇA DE ORDEM)
  // ==================================================================

  /**
   * Gera resposta offline básica quando o LLM não está disponível
   * VERSÃO EXPANDIDA PARA ANÁLISES MULTI-TEMA
   */
  // <--- ESSA FUNÇÃO FOI MOVIDA PARA CIMA DE handleSendMessage
  const generateOfflineResponse = useCallback((query, machineData) => {
    const queryLower = query.toLowerCase();
    const isMultiLine = machineData.tipo_analise === 'multi_linha';
    const themes = machineData.temas_identificados || [];
    let response = `Análise offline ${isMultiLine ? 'de todas as linhas' : `da linha ${selectedLine || DEFAULT_LINE}`}:\n\n`; // Usa linha padrão das variáveis de ambiente

    // Adicionar informações sobre a coleta de dados
    if (machineData.endpoints_sucesso && machineData.endpoints_consultados) {
      response += `📡 **Status da Coleta:**\n`;
      response += `- Endpoints consultados: ${machineData.endpoints_consultados.length}\n`;
      response += `- Sucessos: ${machineData.endpoints_sucesso.length}\n`;
      response += `- Erros: ${machineData.endpoints_erro?.length || 0}\n`;
      response += `- Temas identificados: ${themes.join(', ')}\n\n`;
    }

    if (isMultiLine) {
      if (machineData.dados.eficiencia) {
        const eficiencia = machineData.dados.eficiencia;
        response += `📊 **Análise de Eficiência:**\n`;
        if (eficiencia.ranking_oee && eficiencia.ranking_oee.length > 0) {
          response += `- Melhor linha: ${eficiencia.ranking_oee[0].linha} (OEE: ${eficiencia.ranking_oee[0].valor}%)\n`;
          response += `- Pior linha: ${eficiencia.ranking_oee[eficiencia.ranking_oee.length - 1].linha} (OEE: ${eficiencia.ranking_oee[eficiencia.ranking_oee.length - 1].valor}%)\n`;
          response += `- OEE médio: ${eficiencia.resumo?.oee_medio}%\n\n`;
        }
      }

      if (machineData.dados.qualidade) {
        const qualidade = machineData.dados.qualidade;
        response += `🎯 **Análise de Qualidade:**\n`;
        if (qualidade.ranking_defeitos && qualidade.ranking_defeitos.length > 0) {
          response += `- Melhor qualidade: ${qualidade.ranking_defeitos[qualidade.ranking_defeitos.length - 1].linha} (${qualidade.ranking_defeitos[qualidade.ranking_defeitos.length - 1].taxa_defeitos}% defeitos)\n`;
          response += `- Pior qualidade: ${qualidade.ranking_defeitos[0].linha} (${qualidade.ranking_defeitos[0].taxa_defeitos}% defeitos)\n`;
          response += `- Problemas críticos: ${qualidade.problemas_criticos?.length || 0} linhas\n\n`;
        }
      }

      if (machineData.dados.contexto_completo) {
        const contexto = machineData.dados.contexto_completo;
        response += `📈 **Resumo Geral:**\n`;
        response += `- Total de linhas analisadas: ${contexto.total_linhas}\n`;
        response += `- Tipos de dados disponíveis: ${contexto.tipos_dados_disponiveis?.join(', ')}\n\n`;
      }
    } else {
      if (machineData.dados.kpis) {
        const kpis = machineData.dados.kpis.kpis_principais;
        response += `📊 **KPIs Atuais:**\n`;
        response += `- OEE: ${kpis.oee.valor}% (Meta: ${kpis.oee.meta}%)\n`;
        if (kpis.disponibilidade) response += `- Disponibilidade: ${kpis.disponibilidade.valor}%\n`;
        if (kpis.performance) response += `- Performance: ${kpis.performance.valor}%\n`;
        if (kpis.qualidade) response += `- Qualidade: ${kpis.qualidade.valor}%\n\n`;
      }

      if (machineData.dados.dados_qualidade) {
        const qualidade = machineData.dados.dados_qualidade.metricas_qualidade;
        response += `🎯 **Qualidade:**\n`;
        response += `- Taxa de defeitos: ${qualidade.taxa_defeitos}%\n`;
        if (qualidade.aprovados) response += `- Produtos aprovados: ${qualidade.aprovados}\n\n`;
      }

      if (machineData.dados.variaveis) {
        const variaveis = machineData.dados.variaveis.variaveis;
        response += `🌡️ **Variáveis de Processo:**\n`;
        Object.entries(variaveis).forEach(([nome, dados]) => {
          response += `- ${nome}: ${dados.valor} ${dados.unidade}${dados.alarme ? ' ⚠️' : ''}\n`;
        });
      }
    }

    if (machineData.endpoints_erro && machineData.endpoints_erro.length > 0) {
      response += `\n⚠️ **Problemas na Coleta:**\n`;
      machineData.endpoints_erro.forEach(erro => {
        response += `- ${erro.endpoint}: ${erro.erro}\n`;
      });
    }

    response += `\n⚠️ *Resposta gerada offline. Para análises mais detalhadas, conecte o LLM.*`;
    return response;
  }, [selectedLine]);


  /**
   * Orquestra o envio de uma nova mensagem com coleta de dados multi-tema
   * VERSÃO EXPANDIDA PARA ANÁLISES MULTI-TEMA
   */
  const handleSendMessage = useCallback(async () => {
    if (!currentMessage.trim()) return;

    const userMsg = {
      id: Date.now(),
      type: 'user',
      content: currentMessage.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setCurrentMessage('');
    setIsTyping(true);

    let botResponseContent;

    try {
      const isMultiLineQuery = requiresMultiLineAnalysis(userMsg.content);
      const themes = identifyQueryThemes(userMsg.content);
      const lineToUse = isMultiLineQuery ? 'ALL' : (selectedLine || DEFAULT_LINE); // Usa linha padrão das variáveis de ambiente

      console.log('🎯 Análise da pergunta:', {
        isMultiLine: isMultiLineQuery,
        themes,
        line: lineToUse
      });

      const endpoints = determineDataEndpoints(userMsg.content, lineToUse);

      console.log('📡 Endpoints determinados:', endpoints);

      let machineData = {
        linha: lineToUse,
        status: 'dados_nao_disponiveis',
        motivo: 'API de dados não conectada',
        tipo_analise: isMultiLineQuery ? 'multi_linha' : 'linha_especifica',
        temas_identificados: themes
      };

      if (dataApiConnected) {
        machineData = await collectMachineData(endpoints);
        machineData.temas_identificados = themes;
      } else {
        console.warn('⚠️ API de dados não conectada, tentando conectar...');
        await checkDataApiConnection();
      }

      if (isConnected) {
        botResponseContent = await sendToLlama(userMsg.content, machineData);
      } else {
        // Agora generateOfflineResponse está definida antes de ser chamada aqui.
        if (dataApiConnected && machineData.dados) {
          botResponseContent = generateOfflineResponse(userMsg.content, machineData);
        } else {
          botResponseContent = `Modo Offline: Não foi possível conectar ao LLM (LM API) nem à API de dados. A sua pergunta foi: "${userMsg.content}"\n\nPara resolver:\n1. Verifique se a API de dados está rodando na porta ${DATA_API_ENDPOINT.split(':')[2]}\n2. Verifique se o LM está rodando na porta ${LLAMA_ENDPOINT.split(':')[2]} e configurado para 0.0.0.0\n3. Teste a conectividade com /api/health (API de dados) e /v1/models (LM).`;
        }
      }
    } catch (error) {
      console.error('💥 Erro no processamento da mensagem:', error);
      botResponseContent = `Houve um erro ao processar sua pergunta: ${error.message}\n\nVerifique se os serviços estão rodando corretamente:\n- API de dados: ${settings.dataApiEndpoint}/health\n- LLM : ${settings.llamaEndpoint}/v1/models`;
    }

    const botMsg = {
      id: Date.now() + 1,
      type: 'bot',
      content: botResponseContent,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, botMsg]);
    setIsTyping(false);
  }, [currentMessage, selectedLine, isConnected, dataApiConnected, requiresMultiLineAnalysis, identifyQueryThemes, determineDataEndpoints, collectMachineData, sendToLlama, checkDataApiConnection, settings.dataApiEndpoint, settings.llamaEndpoint, generateOfflineResponse]); // generateOfflineResponse ainda precisa estar nas dependências do useCallback


  const handleKeyPress = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);

  const startListening = useCallback(() => {
    if (recognitionRef.current && speechSupported) {
      setIsListening(true);
      recognitionRef.current.start();
    }
  }, [speechSupported]);

  const clearMessages = useCallback(() => {
    setMessages([{
      id: 1,
      type: 'bot',
      content: 'Histórico limpo. Como posso ajudá-lo com a análise das linhas de produção?',
      timestamp: new Date(),
    }]);
    setLastRequestInfo(null);
  }, []);

  const handleSuggestionClick = useCallback((suggestion) => {
    setCurrentMessage(suggestion);
  }, []);

  // ==================================================================
  // RENDERIZAÇÃO
  // ==================================================================

  const getConnectionBadge = () => {
    const llmStatus = isConnected ? 'success' : 'danger';
    const apiStatus = dataApiConnected ? 'success' : 'warning';

    return (
      <div className="d-flex gap-2 mb-2 flex-wrap">
        <Badge bg={llmStatus}>
          <FaRobot className="me-1" />
          LLM {isConnected ? 'Conectado' : 'Offline'}
        </Badge>
        <Badge bg={apiStatus}>
          <FaDatabase className="me-1" />
          API {dataApiConnected ? 'Conectada' : 'Offline'}
        </Badge>
        <Badge bg="info">
          <FaBalanceScale className="me-1" />
          Multi-Linha
        </Badge>
        <Badge bg="secondary">
          <FaLayerGroup className="me-1" />
          Multi-Tema
        </Badge>
        {lastRequestInfo && (
          <Badge bg="dark">
            <FaSearch className="me-1" />
            {lastRequestInfo.endpoints_sucesso}/{lastRequestInfo.endpoints_total} OK
          </Badge>
        )}
      </div>
    );
  };

  const renderMessage = (message) => {
    const isBot = message.type === 'bot';
    return (
      <div key={message.id} className={`message ${isBot ? 'bot-message' : 'user-message'}`}>
        <div className="message-header">
          {isBot ? <FaRobot /> : <FaUser />}
          <span className="message-time">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>
        <div className="message-content">
          <div dangerouslySetInnerHTML={{ __html: marked.parse(message.content) }} />
        </div>
      </div>
    );
  };

  return (
    <Card className="machine-chat-card h-100">
      {/* --- CABEÇALHO DO CARD REVISADO PARA INCLUIR LIIA E ÍCONE --- */}
      <Card.Header className="machine-chat-header-custom d-flex justify-content-between align-items-center">
        <div className="d-flex align-items-center flex-grow-1">
          <div className="liia-icon-container">
            <FaBrain className="liia-icon-brain" /> {/* Usando FaBrain */}
            {/* Fallback se FaBrain não estiver disponível: <FaRobot className="liia-icon-robot" /> */}
            <span className="liia-name">{AI_NAME}</span>
          </div>
          <h5 className="mb-0 ms-3 d-none d-md-block">
            Chat IA Industrial - Análise Multi-Linha & Multi-Tema
          </h5>
        </div>
        <div className="d-flex gap-2 align-items-center">
          {getConnectionBadge()} {/* Mantenha os badges de conexão aqui, se quiser. */}
          <OverlayTrigger
            placement="bottom"
            overlay={<Tooltip>Testar conectividade</Tooltip>}
          >
            <Button variant="outline-info" size="sm" onClick={testEndpointConnectivity}>
              <FaSearch />
            </Button>
          </OverlayTrigger>
          <OverlayTrigger
            placement="bottom"
            overlay={<Tooltip>Limpar histórico</Tooltip>}
          >
            <Button variant="outline-secondary" size="sm" onClick={clearMessages}>
              <FaTrash />
            </Button>
          </OverlayTrigger>
          {/* Configurações (endpoint LLM e API de dados) — só superusuário */}
          {isSuperuser && (
            <OverlayTrigger
              placement="bottom"
              overlay={<Tooltip>Configurações (endpoint LLM / dados)</Tooltip>}
            >
              <Button variant="outline-primary" size="sm" onClick={() => setShowSettingsModal(true)}>
                <FaCog />
              </Button>
            </OverlayTrigger>
          )}
        </div>
      </Card.Header>
      {/* --- FIM DO CABEÇALHO DO CARD REVISADO --- */}

      <Card.Body className="d-flex flex-column p-0">
        {/* Área de sugestões */}
        {settings.showSuggestions && suggestions.length > 0 && (
          <div className="suggestions-area p-3 border-bottom">
            <small className="text-muted d-flex align-items-center mb-2">
              <FaLightbulb className="me-1" />
              Sugestões de perguntas (linha específica, multi-linha e multi-tema):
            </small>
            <div className="d-flex flex-wrap gap-1">
              {suggestions.slice(0, 8).map((suggestion, index) => (
                <Button
                  key={index}
                  variant="outline-info"
                  size="sm"
                  onClick={() => handleSuggestionClick(suggestion)}
                  className="suggestion-btn"
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Área de mensagens */}
        <div className="messages-area flex-grow-1 p-3">
          {messages.map(renderMessage)}
          {isTyping && (
            <div className="message bot-message">
              <div className="message-header">
                <FaRobot />
                <span className="message-time">Analisando...</span>
              </div>
              <div className="message-content">
                <Spinner animation="border" size="sm" className="me-2" />
                Coletando dados de múltiplas fontes e analisando...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Área de input */}
        <div className="input-area p-3 border-top">
          {!dataApiConnected && (
            <Alert variant="warning" className="mb-2">
              <FaExclamationTriangle className="me-2" />
              API de dados offline. Verifique se o servidor está rodando na porta {DATA_API_ENDPOINT.split(':')[2]}.
            </Alert>
          )}

          <InputGroup>
            <Form.Control
              as="textarea"
              rows={2}
              placeholder={selectedLine ?
                `Digite sua pergunta sobre a linha ${selectedLine} ou sobre todas as linhas (suporte multi-tema)...` :
                "Digite sua pergunta sobre as linhas de produção (análises multi-linha e multi-tema)..."
              }
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isTyping}
            />
            {speechSupported && (
              <Button
                variant={isListening ? "danger" : "outline-secondary"}
                onClick={startListening}
                disabled={isTyping || isListening}
              >
                {isListening ? <FaMicrophoneSlash /> : <FaMicrophone />}
              </Button>
            )}
            <Button
              variant="primary"
              onClick={handleSendMessage}
              disabled={!currentMessage.trim() || isTyping}
            >
              <FaPaperPlane />
            </Button>
          </InputGroup>
        </div>
      </Card.Body>

      {/* Modal de configurações — só superusuário (reforço além de esconder o botão) */}
      <Modal show={showSettingsModal && isSuperuser} onHide={() => setShowSettingsModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Configurações do Chat IA</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Endpoint do LLM (API)</Form.Label>
              <Form.Control
                type="text"
                value={settings.llamaEndpoint}
                onChange={(e) => setSettings(prev => ({ ...prev, llamaEndpoint: e.target.value }))}
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Endpoint da API de Dados (Flask)</Form.Label>
              <Form.Control
                type="text"
                value={settings.dataApiEndpoint}
                onChange={(e) => setSettings(prev => ({ ...prev, dataApiEndpoint: e.target.value }))}
              />
            </Form.Group>
            <Form.Check
              type="checkbox"
              label="Mostrar sugestões"
              checked={settings.showSuggestions}
              onChange={(e) => setSettings(prev => ({ ...prev, showSuggestions: e.target.checked }))}
            />
            {lastRequestInfo && (
              <div className="mt-3">
                <h6>Última Requisição:</h6>
                <small className="text-muted">
                  {lastRequestInfo.endpoints_sucesso}/{lastRequestInfo.endpoints_total} endpoints OK<br />
                  Dados: {lastRequestInfo.dados_coletados.join(', ')}<br />
                  {lastRequestInfo.timestamp}
                </small>
              </div>
            )}
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowSettingsModal(false)}>
            Fechar
          </Button>
        </Modal.Footer>
      </Modal>
    </Card>
  );
};

export default MachineChat;

