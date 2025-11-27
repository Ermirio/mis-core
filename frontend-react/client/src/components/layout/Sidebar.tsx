import React, { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import "./Sidebar.css";

const Sidebar: React.FC = () => {
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

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <Link to="/" className="sidebar-title-link">
          <h2 className="sidebar-title">MIS - CORE</h2>
        </Link>
        <p className="sidebar-subtitle">Monitoramento Industrial</p>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
          end
        >
          🏠 Home
        </NavLink>

        <NavLink
          to="/dashboard-fabrica"
          className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
        >
          🏢 Gestão Fábrica
        </NavLink>

        <div className="sidebar-divider"></div>
        <p className="sidebar-section-title">LINHAS DE PRODUÇÃO</p>

        {loading ? (
          <p className="sidebar-loading">Carregando...</p>
        ) : (
          linhas.map((linha) => (
            <NavLink
              key={linha.id}
              to={`/linha/${linha.id}`}
              className={({ isActive }) =>
                isActive ? "sidebar-link active" : "sidebar-link"
              }
            >
              🏭 {linha.nome}
            </NavLink>
          ))
        )}
      </nav>
    </div>
  );
};

export default Sidebar;
