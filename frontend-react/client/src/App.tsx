import { BrowserRouter, Navigate, Outlet, Routes, Route, useLocation } from "react-router-dom";
import MainLayout from "./components/layout/MainLayout";

import Home from "./pages/HomeV2";
import LinhaDetalhes from "./pages/LinhaDetalhes.tsx";
import EquipamentoDetalhes from "./pages/EquipamentoDetalhes.tsx";
import DiagnosticosLogs from "./pages/DiagnosticosLogs";
import LineManagement from "./pages/LineManagement.tsx";
import LineDeepView from "./pages/LineDeepView";
import FactoryManagementPanel from "./pages/FactoryManagementPanel";
import LineAnalytics from "./pages/LineAnalytics";
import WasteAnalysisDashboard from "./pages/WasteAnalysisDashboard";
import GiveAwayDashboard from "./pages/GiveAwayDashboard";

import Login from "./pages/Login";

import AdminLayout from "./pages/admin/AdminLayout";
import AdminDashboard from "./pages/admin/AdminDashboard";
import EquipmentsAdmin from "./pages/admin/EquipmentsAdmin";
import TagsAdmin from "./pages/admin/TagsAdmin";
import ProductsAdmin from "./pages/admin/ProductsAdmin";
import ProductionOrdersAdmin from "./pages/admin/ProductionOrdersAdmin";
import FactoryHierarchy from "./pages/admin/FactoryHierarchy";
import OPCConnectionsAdmin from "./pages/admin/OPCConnectionsAdmin";
import ProductionCalendarAdmin from "./pages/admin/ProductionCalendarAdmin";

import { useEffect, useState } from "react";
import SplashScreen from "./components/SplashScreen";
import { DJANGO_API_URL } from "./config/api";

type AuthState = "checking" | "authenticated" | "anonymous";

function RequireAuthentication() {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const location = useLocation();

  useEffect(() => {
    let alive = true;
    fetch(`${DJANGO_API_URL}/auth/me/`, { credentials: "include" })
      .then((response) => {
        if (alive) setAuthState(response.ok ? "authenticated" : "anonymous");
      })
      .catch(() => {
        if (alive) setAuthState("anonymous");
      });
    return () => { alive = false; };
  }, []);

  if (authState === "checking") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-700">
        Validando acesso...
      </div>
    );
  }

  if (authState === "anonymous") {
    const next = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return <Outlet />;
}

function App() {
  const [showSplash, setShowSplash] = useState(
    () => !window.location.pathname.endsWith('/login'),
  );

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      {showSplash ? (
        <SplashScreen onComplete={() => setShowSplash(false)} />
      ) : (
        <Routes>
          {/* Rotas Públicas */}
          <Route path="/login" element={<Login />} />

          <Route element={<RequireAuthentication />}>
            {/* Rotas Protegidas do Hub */}
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
              <Route path="giveaway" element={<GiveAwayDashboard />} />
            </Route>

            {/* Admin Routes (Standalone Layout) */}
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminDashboard />} />
              <Route path="equipamentos" element={<EquipmentsAdmin />} />
              <Route path="tags" element={<TagsAdmin />} />
              <Route path="produtos" element={<ProductsAdmin />} />
              <Route path="ordens" element={<ProductionOrdersAdmin />} />
              <Route path="hierarquia" element={<FactoryHierarchy />} />
              <Route path="conexoes-opc" element={<OPCConnectionsAdmin />} />
              <Route path="calendario" element={<ProductionCalendarAdmin />} />
            </Route>
          </Route>
        </Routes>
      )}
    </BrowserRouter>
  );
}

export default App;
