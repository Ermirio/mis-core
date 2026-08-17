/**
 * App.js - Componente principal da aplicação (Versão Compatível)
 * 
 * Versão conservadora que mantém toda a funcionalidade original
 * com melhorias visuais mínimas e compatibilidade total.
 * Mantém o header original "MIS Developed By Process Engineer".
 * 
 * @author Process Engineer
 * @version 3.1.1 - Implementação de Autenticação JWT
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext'; // Importar AuthProvider
import ProtectedRoute from './components/ProtectedRoute'; // Importar ProtectedRoute
import LoginPage from './components/LoginPage'; // Importar LoginPage
import useAxios from './hooks/useAxios'; // Para polling de não lidas

// Componentes de layout
import Navbar from './components/layout/Navbar';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header'; // Header original mantido

// Componentes de conteúdo existentes
import KpisContent from './components/KpisContent';
// [v10.2] Tela "Status do Produto" desativada temporariamente.
// O worker do Django (OPCValidacaoQualidadeWorker) continua rodando para a
// Validação de Qualidade, mas a tela em si foi escondida.
// Para REATIVAR: descomente o import + a rota abaixo + o NavLink em Header.jsx.
// import ProductStatusContent from './components/ProductStatusContent';
import TrocaAutomaticaContent from './components/TrocaAutomaticaContent';
import TrocasContent from './components/TrocasContent'; // Descomentado para uso

import FlexiveisContent from './components/FlexiveisContent';
import CartuchoContent from './components/CartuchoContent';

// Novos componentes implementados
import ProcessVariablesContent from './components/ProcessVariablesContent';
import AndrettiContent from './components/AndrettiContent';
import MachineChat from './components/MachineChat';
import HistoricoDataContent from './components/HistoricoDataContent'; // Componente de histórico de dados
import IntertravamentosContent from './components/IntertravamentosContent'; // Módulo de Intertravamentos
import ValidacoesContent from './components/ValidacoesContent'; // Módulo de Validações v9.0
import ComunicacaoContent from './components/ComunicacaoContent'; // Central de Comunicação v9.2
import ReceitaMonitorContent from './components/ReceitaMonitorContent'; // Recipe Monitor (mis-recipe-intelligent)
import GestaoUsuariosContent from './components/GestaoUsuariosContent'; // Gestão de usuários (só superuser)

// Estilos
import './styles/App.css';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Componente de Conteúdo Principal (sem o Router)
 */
const AppContent = () => {
  // ===== ESTADOS DO COMPONENTE =====

  /**
   * Estado para a linha selecionada
   */
  const [selectedLine, setSelectedLine] = useState(null);

  /**
   * Estado para controle da sidebar
   */
  const [sidebarVisible, setSidebarVisible] = useState(true);

  /**
   * Mensagens não lidas por linha { L01: 3, L02: 0, ... }
   * Usa useAxios para garantir auth header e baseURL idênticos ao resto da app.
   */
  const api = useAxios();
  const apiRef = useRef(api);
  apiRef.current = api;

  const [unreadCounts, setUnreadCounts] = useState({});

  const fetchUnreadCounts = useCallback(async () => {
    try {
      const res = await apiRef.current.get('/api/chat/nao-lidas-por-linha/');
      setUnreadCounts(res.data || {});
    } catch (_) {}
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchUnreadCounts();
    const id = setInterval(fetchUnreadCounts, 30000);
    return () => clearInterval(id);
  }, [fetchUnreadCounts]);

  /** Chamado pelo ComunicacaoContent após abrir o chat de uma linha */
  const handleMarkRead = useCallback((linha) => {
    setUnreadCounts(prev => ({ ...prev, [linha]: 0 }));
    // Também dispara uma re-busca para sincronizar com o servidor
    setTimeout(fetchUnreadCounts, 500);
  }, [fetchUnreadCounts]);

  // ===== MANIPULADORES DE EVENTOS =====

  /**
   * Manipula a seleção de uma linha
   */
  const handleSelectLine = useCallback((line) => {
    console.log(`Linha selecionada: ${line}`);
    setSelectedLine(line);
  }, []);

  /**
   * Manipula o toggle da sidebar
   */
  const handleToggleSidebar = useCallback(() => {
    setSidebarVisible(prev => !prev);
  }, []);

  // ===== RENDERIZAÇÃO PRINCIPAL =====
  return (
    <div className="app-container">
      {/* Sidebar de navegação lateral */}
      <Sidebar
        selectedLine={selectedLine}
        onSelectLine={handleSelectLine}
        visible={sidebarVisible}
        unreadCounts={unreadCounts}
      />

      {/* Container principal de conteúdo */}
      <main className={`main-content ${sidebarVisible ? 'sidebar-open' : 'sidebar-closed'}`}>
        {/* Barra de notificações e usuário */}
        <Navbar
          selectedLine={selectedLine}
          onToggleSidebar={handleToggleSidebar}
          sidebarVisible={sidebarVisible}
        />

        {/* Header original mantido - "MIS Developed By Process Engineer" */}
        <Header unreadCounts={unreadCounts} />

        <div className="content-area">
          <Routes>
            {/* Rota de Login (Não Protegida) */}
            <Route path="/login" element={<LoginPage />} />

            {/* Rotas Protegidas */}
            <Route element={<ProtectedRoute />}>
              {/* Rota padrão redireciona para Troca Automática (Status Produto desativado v10.2) */}
              <Route path="/" element={<Navigate to="/troca-automatica" replace />} />

              {/* Rotas principais existentes */}
              <Route
                path="/kpis"
                element={<KpisContent selectedLine={selectedLine} />}
              />
              {/* [v10.2] Tela Status do Produto desativada.
                  Para REATIVAR: descomente abaixo + import em App.js + NavLink em Header.jsx.
              <Route
                path="/product-status"
                element={<ProductStatusContent selectedLine={selectedLine} />}
              />
              */}
              <Route
                path="/troca-automatica"
                element={<TrocaAutomaticaContent selectedLine={selectedLine} />}
              />
              <Route
                path="/trocas"
                element={<TrocasContent selectedLine={selectedLine} />}
              />

              <Route
                path="/flexiveis"
                element={<FlexiveisContent selectedLine={selectedLine} />}
              />
              <Route
                path="/cartucho"
                element={<CartuchoContent selectedLine={selectedLine} />}
              />

              {/* Novas rotas implementadas */}
              <Route
                path="/process-variables"
                element={<ProcessVariablesContent selectedLine={selectedLine} />}
              />
              <Route
                path="/andretti"
                element={<AndrettiContent selectedLine={selectedLine} />}
              />
              <Route
                path="/machine-chat"
                element={<MachineChat selectedLine={selectedLine} />}
              />
              <Route
                path="/historico-data"
                element={<HistoricoDataContent selectedLine={selectedLine} />}
              />
              <Route
                path="/intertravamentos"
                element={<IntertravamentosContent selectedLine={selectedLine} />}
              />
              <Route
                path="/validacoes"
                element={<ValidacoesContent selectedLine={selectedLine} />}
              />
              <Route
                path="/comunicacao"
                element={
                  <ComunicacaoContent
                    selectedLine={selectedLine}
                    onMarkRead={handleMarkRead}
                  />
                }
              />

              {/* Recipe Monitor — leitura OPC contínua + sincronismo de receita */}
              <Route
                path="/receita-monitor"
                element={<ReceitaMonitorContent selectedLine={selectedLine} />}
              />

              {/* Gestão de Usuários — só superuser (o componente também valida) */}
              <Route
                path="/gestao-usuarios"
                element={<GestaoUsuariosContent />}
              />

              {/* Rota de fallback (Status Produto desativado v10.2 → troca-automatica) */}
              <Route path="*" element={<Navigate to="/troca-automatica" replace />} />
            </Route>
          </Routes>
        </div>
      </main>
    </div>
  );
};

/**
 * Componente principal que envolve o AppContent com o Router e AuthProvider
 */
const App = () => (
  <Router basename="/mis-change-over">
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  </Router>
);

export default App;
