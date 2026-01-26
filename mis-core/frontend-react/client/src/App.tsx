import { BrowserRouter, Routes, Route } from "react-router-dom";
import MainLayout from "./components/layout/MainLayout";

import Home from "./pages/Home";
import LinhaDetalhes from "./pages/LinhaDetalhes.tsx";
import EquipamentoDetalhes from "./pages/EquipamentoDetalhes.tsx";
import DiagnosticosLogs from "./pages/DiagnosticosLogs";
import LineManagement from "./pages/LineManagement.tsx";
import LineDeepView from "./pages/LineDeepView";
import FactoryManagementPanel from "./pages/FactoryManagementPanel";
import LineAnalytics from "./pages/LineAnalytics";
import WasteAnalysisDashboard from "./pages/WasteAnalysisDashboard";

import React, { useState } from "react";
import SplashScreen from "./components/SplashScreen";

function App() {
  const [showSplash, setShowSplash] = useState(true);

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      {showSplash ? (
        <SplashScreen onComplete={() => setShowSplash(false)} />
      ) : (
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Home />} />
            <Route path="linha/:linhaId" element={<LinhaDetalhes />} />
            <Route path="linha/:linhaId/detalhes" element={<LineDeepView />} />
            <Route path="equipamento/:equipamentoId" element={<EquipamentoDetalhes />} />
            <Route path="factory-panel" element={<FactoryManagementPanel />} />
            <Route path="diagnosticos" element={<DiagnosticosLogs />} />
            <Route path="linha-management/:linhaId" element={<LineManagement />} />
            <Route path="analytics" element={<LineAnalytics />} />
            <Route path="descartes" element={<WasteAnalysisDashboard />} />
          </Route>
        </Routes>
      )}
    </BrowserRouter>
  );
}

export default App;
