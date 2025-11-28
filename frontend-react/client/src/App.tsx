import { BrowserRouter, Routes, Route } from "react-router-dom";
import MainLayout from "./components/layout/MainLayout";

import Home from "./pages/Home";
import FactoryDashboard from "./pages/FactoryDashboard";
import FabricaDetalhes from "./pages/FabricaDetalhes";
import LinhaDetalhes from "./pages/LinhaDetalhes.tsx";
import EquipamentoDetalhes from "./pages/EquipamentoDetalhes.tsx";
import FactoryManagement from "./pages/FactoryManagement";
import DiagnosticosLogs from "./pages/DiagnosticosLogs";
import LineManagement from "./pages/LineManagement.tsx";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Home />} />
          <Route path="dashboard-fabrica" element={<FactoryDashboard />} />
          <Route path="fabrica" element={<FabricaDetalhes />} />
          <Route path="linha/:linhaId" element={<LinhaDetalhes />} />
          <Route path="equipamento/:equipamentoId" element={<EquipamentoDetalhes />} />
            <Route path="factory-management" element={<FactoryManagement />} />
          <Route path="diagnosticos" element={<DiagnosticosLogs />} />
          <Route path="linha-management/:linhaId" element={<LineManagement />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
