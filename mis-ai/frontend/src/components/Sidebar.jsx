import React from 'react'
import { NavLink, Link } from 'react-router-dom'
import {
    ChevronLeft,
    ChevronRight,
    Home,
    Settings,
    Activity,
    Database,
    TrendingUp,
    BarChart3,
    Search,
    Zap,
    Play
} from 'lucide-react'
import './Sidebar.css'

const Sidebar = ({ collapsed, onToggle }) => {
    // Use absolute path for public assets in Vite
    const logoSrc = "/mis-ai/logo.png";

    return (
        <div className={`sidebar ${collapsed ? "collapsed" : ""}`}>
            <div className="sidebar-header">
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
                            src={logoSrc}
                            alt="MIS-AI"
                            className="sidebar-logo"
                        />
                        <p className="sidebar-subtitle">Generic Prediction System</p>
                    </Link>
                )}
            </div>

            <nav className="sidebar-nav">
                <NavLink
                    to="/dashboard"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Dashboard"
                >
                    <Home size={20} />
                    {!collapsed && <span>Dashboard</span>}
                </NavLink>

                <div className="sidebar-divider"></div>
                {!collapsed && <p className="sidebar-section-title">Gerenciamento</p>}

                <NavLink
                    to="/lines"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Linhas"
                >
                    <Activity size={20} />
                    {!collapsed && <span>Linhas</span>}
                </NavLink>

                <NavLink
                    to="/targets"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Targets"
                >
                    <Zap size={20} />
                    {!collapsed && <span>Targets</span>}
                </NavLink>

                <NavLink
                    to="/models"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Modelos"
                >
                    <BarChart3 size={20} />
                    {!collapsed && <span>Modelos</span>}
                </NavLink>

                <div className="sidebar-divider"></div>
                {!collapsed && <p className="sidebar-section-title">Predição & Dados</p>}

                <NavLink
                    to="/prediction"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Predições"
                >
                    <TrendingUp size={20} />
                    {!collapsed && <span>Predições</span>}
                </NavLink>

                <NavLink
                    to="/simulation"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Simulador"
                >
                    <Play size={20} />
                    {!collapsed && <span>Simulador</span>}
                </NavLink>

                <NavLink
                    to="/analysis"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Análise Detalhada"
                >
                    <Search size={20} />
                    {!collapsed && <span>Análise Detalhada</span>}
                </NavLink>

                <NavLink
                    to="/data"
                    className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                    title="Coleta de Dados"
                >
                    <Database size={20} />
                    {!collapsed && <span>Coleta de Dados</span>}
                </NavLink>

                <div className="sidebar-footer">
                    <NavLink
                        to="/opc"
                        className={({ isActive }) => isActive ? "sidebar-link active" : "sidebar-link"}
                        title="Configuração OPC"
                    >
                        <Settings size={20} />
                        {!collapsed && <span>Configuração OPC</span>}
                    </NavLink>
                </div>
            </nav>
        </div>
    )
}

export default Sidebar
