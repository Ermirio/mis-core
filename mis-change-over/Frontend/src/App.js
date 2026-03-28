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

import React, { useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext'; // Importar AuthProvider
import ProtectedRoute from './components/ProtectedRoute'; // Importar ProtectedRoute
import LoginPage from './components/LoginPage'; // Importar LoginPage

// Componentes de layout
import Navbar from './components/layout/Navbar';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header'; // Header original mantido

// Componentes de conteúdo existentes
import KpisContent from './components/KpisContent';
import ProductStatusContent from './components/ProductStatusContent';
import TrocaAutomaticaContent from './components/TrocaAutomaticaContent';
import TrocasContent from './components/TrocasContent'; // Descomentado para uso

import FlexiveisContent from './components/FlexiveisContent';
import CartuchoContent from './components/CartuchoContent';

// Novos componentes implementados
import ProcessVariablesContent from './components/ProcessVariablesContent';
import ReportsContent from './components/ReportsContent';
import MachineChat from './components/MachineChat';
import HistoricoDataContent from './components/HistoricoDataContent'; // Componente de histórico de dados
import IntertravamentosContent from './components/IntertravamentosContent'; // Módulo de Intertravamentos

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
        <Header />

        <div className="content-area">
          <Routes>
            {/* Rota de Login (Não Protegida) */}
            <Route path="/login" element={<LoginPage />} />

            {/* Rotas Protegidas */}
            <Route element={<ProtectedRoute />}>
              {/* Rota padrão redireciona para KPIs */}
              <Route path="/" element={<Navigate to="/kpis" replace />} />

              {/* Rotas principais existentes */}
              <Route
                path="/kpis"
                element={<KpisContent selectedLine={selectedLine} />}
              />
              <Route
                path="/product-status"
                element={<ProductStatusContent selectedLine={selectedLine} />}
              />
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
                path="/reports"
                element={<ReportsContent selectedLine={selectedLine} />}
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

              {/* Rota de fallback */}
              <Route path="*" element={<Navigate to="/kpis" replace />} />
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
