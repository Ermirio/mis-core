import React, { useState } from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import {
    LayoutDashboard,
    Server,
    Tag,
    Package,
    ClipboardList,
    Layers,
    Wifi,
    ChevronLeft,
    ChevronRight,
    Home,
    Calendar
} from "lucide-react";

const AdminLayout: React.FC = () => {
    const location = useLocation();
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

    const menuItems = [
        { path: "/admin", icon: <LayoutDashboard className="w-5 h-5" />, label: "Dashboard" },
        { path: "/admin/hierarquia", icon: <Layers className="w-5 h-5" />, label: "Hierarquia" },
        { path: "/admin/equipamentos", icon: <Server className="w-5 h-5" />, label: "Equipamentos" },
        { path: "/admin/tags", icon: <Tag className="w-5 h-5" />, label: "Tags OPC" },
        { path: "/admin/produtos", icon: <Package className="w-5 h-5" />, label: "Produtos" },
        { path: "/admin/ordens", icon: <ClipboardList className="w-5 h-5" />, label: "Ordens de Produção" },
        { path: "/admin/calendario", icon: <Calendar className="w-5 h-5" />, label: "Calendário de Produção" },
        { path: "/admin/conexoes-opc", icon: <Wifi className="w-5 h-5" />, label: "Conexões OPC" },
    ];

    return (
        <div className="admin-layout flex h-screen w-full bg-neutral-900 text-neutral-200">
            {/* Sidebar */}
            <aside
                className={`
                    bg-neutral-950 border-r border-neutral-800 transition-all duration-300 flex flex-col
                    ${sidebarCollapsed ? 'w-16' : 'w-64'}
                `}
            >
                {/* Header */}
                <div className="p-4 border-b border-neutral-800">
                    {!sidebarCollapsed ? (
                        <div>
                            <h1 className="text-lg font-bold text-neutral-100 tracking-tight">
                                MIS-CORE <span className="text-emerald-500">ADMIN</span>
                            </h1>
                            <p className="text-xs text-neutral-500 uppercase tracking-widest mt-1">
                                High Performance
                            </p>
                        </div>
                    ) : (
                        <div className="flex justify-center">
                            <div className="w-8 h-8 bg-emerald-500 rounded-md flex items-center justify-center">
                                <span className="text-white font-bold text-sm">M</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Navigation */}
                <nav className="flex-1 overflow-y-auto py-4">
                    <div className="space-y-1 px-2">
                        {menuItems.map((item) => {
                            const isActive = location.pathname === item.path;
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    className={`
                                        flex items-center gap-3 px-3 py-2 rounded-md transition-all
                                        ${isActive
                                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/50'
                                            : 'text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200'
                                        }
                                        ${sidebarCollapsed ? 'justify-center' : ''}
                                    `}
                                    title={sidebarCollapsed ? item.label : ''}
                                >
                                    {item.icon}
                                    {!sidebarCollapsed && (
                                        <span className="text-sm font-medium">{item.label}</span>
                                    )}
                                </Link>
                            );
                        })}
                    </div>
                </nav>

                {/* Footer */}
                <div className="p-4 border-t border-neutral-800">
                    <Link
                        to="/"
                        className="flex items-center gap-3 px-3 py-2 rounded-md text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 transition-all"
                        title={sidebarCollapsed ? 'Voltar ao Dashboard Principal' : ''}
                    >
                        <Home className="w-5 h-5" />
                        {!sidebarCollapsed && <span className="text-sm">Dashboard Principal</span>}
                    </Link>
                    <button
                        onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                        className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-neutral-500 hover:bg-neutral-800 hover:text-neutral-300 transition-all"
                    >
                        {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                        {!sidebarCollapsed && <span className="text-xs">Recolher</span>}
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Top Bar */}
                <header className="admin-header flex items-center justify-between px-6 py-4 border-b border-neutral-800 bg-neutral-950">
                    <div className="flex items-center gap-4">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                        <span className="text-xs text-neutral-600">
                            System Mode: <span className="text-emerald-400 font-mono">ONLINE</span>
                        </span>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="text-xs text-neutral-600">
                            {new Date().toLocaleString('pt-BR')}
                        </span>
                    </div>
                </header>

                {/* Content Area */}
                <main className="admin-content flex-1 overflow-auto p-6 bg-neutral-900">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};

export default AdminLayout;
