import React, { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Menu } from "lucide-react";
import { useSystemHealth } from "../../hooks/useSystemHealth";
import "./Sidebar.css";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const DJANGO_API_URL =
    import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";

  const [linhas, setLinhas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchLinhas() {
      try {
        const resp = await fetch(`${DJANGO_API_URL}/linhas/`);
        const data = await resp.json();
        setLinhas(data.results || data);
      } catch (err) {
        console.error("Erro ao carregar linhas:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchLinhas();
  }, [DJANGO_API_URL]);

  const { health } = useSystemHealth();

  return (
    <div className={`sidebar ${collapsed ? "collapsed" : ""}`}>

      <div className="sidebar-header">
        {/* Toggle Button */}
        <button
          onClick={onToggle}
          className="sidebar-toggle"
          title={collapsed ? "Expandir" : "Recolher"}
        >
          {collapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
        </button>

        {!collapsed && (
          <Link to="/" className="sidebar-title-link">
            <img
              src={`${import.meta.env.BASE_URL}mis-core-logo-v2.png`}
              alt="MIS-CORE"
              className="sidebar-logo"
            />
            <p className="sidebar-subtitle">Monitoramento Industrial</p>
          </Link>
        )}
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
          end
          title="Home"
        >
          <span>🏠</span>
          {!collapsed && <span>Home</span>}
        </NavLink>

        <NavLink
          to="/factory-panel"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
          title="Gestão Fabril"
        >
          <span>🏢</span>
          {!collapsed && <span>Gestão Fabril</span>}
        </NavLink>

        <NavLink
          to="/analytics"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
          title="Analytics"
        >
          <span>📊</span>
          {!collapsed && <span>Analytics</span>}
        </NavLink>

        <NavLink
          to="/descartes"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
          title="Análise de Descartes"
        >
          <span>🗑️</span>
          {!collapsed && <span>Descartes</span>}
        </NavLink>

        <NavLink
          to="/giveaway"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
          title="Gestão de Give Away"
        >
          <span>⚖️</span>
          {!collapsed && <span>Give Away</span>}
        </NavLink>

        <div className="sidebar-divider"></div>
        {!collapsed && <p className="sidebar-section-title">LINHAS DE PRODUÇÃO</p>}

        {loading ? (
          !collapsed && <p className="sidebar-loading">Carregando...</p>
        ) : (
          linhas.map((linha) => (
            <NavLink
              key={linha.id}
              to={`/linha/${linha.codigo || linha.id}/detalhes`}
              className={({ isActive }) =>
                isActive ? "sidebar-link active" : "sidebar-link"
              }
              title={linha.nome}
            >
              <span>🏭</span>
              {!collapsed && <span>{linha.nome}</span>}
            </NavLink>
          ))
        )}
      </nav>

      <div className="sidebar-footer">
        <NavLink
          to="/admin"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
          title="Configurações (Admin)"
          to="/admin"
          className={({ isActive }) => isActive || window.location.pathname.startsWith('/admin') ? "sidebar-link active" : "sidebar-link"}
          title="Configurações (Admin)"
        >
          <span>⚙️</span>
          {!collapsed && <span>Configurações</span>}
        </NavLink>

        <NavLink
          to="/diagnosticos"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? "active" : ""} ${health === 'critical' ? 'critical-pulse' : health === 'warning' ? 'warning-glow' : ''}`
          }
          title={health === 'critical' ? 'Erro no Sistema' : health === 'warning' ? 'Alertas Ativos' : 'Diagnósticos'}
        >
          <span>{health === 'critical' ? '🚨' : health === 'warning' ? '⚠️' : '🔧'}</span>
          {!collapsed && <span>Diagnósticos</span>}
        </NavLink>
      </div>
    </div>
  );
};

export default Sidebar;
