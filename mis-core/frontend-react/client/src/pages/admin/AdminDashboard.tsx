import React from "react";
import { Link } from "react-router-dom";
import { Settings, Database, Activity, Server, Cpu } from "lucide-react";

// ISA 101 Concept: High Performance Dashboard
// - Dark background to reduce glare
// - High contrast for active data / alerts
// - Low contrast for structure/containers

const AdminDashboard: React.FC = () => {
    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-semibold text-neutral-100">Visão Geral do Sistema</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <DashboardCard
                    title="Equipamentos"
                    value="12"
                    subtext="3 Offline"
                    icon={<Server className="w-6 h-6 text-emerald-500" />}
                    link="/admin/equipamentos"
                />
                <DashboardCard
                    title="Tags OPC"
                    value="1,240"
                    subtext="15KB/s Ingestion"
                    icon={<Activity className="w-6 h-6 text-blue-500" />}
                    link="/admin/tags"
                />
                <DashboardCard
                    title="Banco de Dados"
                    value="InfluxDB"
                    subtext="Healthy (15ms)"
                    icon={<Database className="w-6 h-6 text-purple-500" />}
                    link="/admin/database"
                />
                <DashboardCard
                    title="Status Geral"
                    value="98.5%"
                    subtext="Uptime (30d)"
                    icon={<Cpu className="w-6 h-6 text-green-500" />}
                    link="/diagnosticos"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Quick Actions / Recent Activity Placeholder */}
                <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6">
                    <h3 className="text-lg font-medium text-neutral-300 mb-4">Ações Rápidas</h3>
                    <div className="space-y-3">
                        <QuickActionButton label="Gerenciar Equipamentos" to="/admin/equipamentos" />
                        <QuickActionButton label="Planejamento de Produção" to="/admin/ordens" />
                        <QuickActionButton label="Catálogo de Produtos" to="/admin/produtos" />
                        <QuickActionButton label="Gerenciar Usuários" to="/admin/users" />
                        <QuickActionButton label="Ver Logs de Erro" to="/diagnosticos" />
                    </div>
                </div>

                <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6">
                    <h3 className="text-lg font-medium text-neutral-300 mb-4">Diagnóstico Rápido</h3>
                    <div className="space-y-4 text-sm text-neutral-400">
                        <div className="flex justify-between items-center border-b border-neutral-800 pb-2">
                            <span>API Latency</span>
                            <span className="font-mono text-emerald-400">45ms</span>
                        </div>
                        <div className="flex justify-between items-center border-b border-neutral-800 pb-2">
                            <span>OPC Collector Status</span>
                            <span className="font-mono text-emerald-400">CONNECTED</span>
                        </div>
                        <div className="flex justify-between items-center border-b border-neutral-800 pb-2">
                            <span>Last Backup</span>
                            <span className="font-mono text-neutral-500">2 hours ago</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

const DashboardCard: React.FC<{ title: string; value: string; subtext: string; icon: React.ReactNode; link: string }> = ({ title, value, subtext, icon, link }) => (
    <Link to={link} className="block group">
        <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6 hover:border-emerald-500/50 transition-colors duration-200">
            <div className="flex justify-between items-start mb-4">
                <div className="p-2 bg-neutral-900 rounded-md border border-neutral-800 group-hover:border-neutral-700 transition-colors">
                    {icon}
                </div>
                {/* Indicator Dot */}
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            </div>
            <div className="space-y-1">
                <span className="text-sm font-medium text-neutral-500 uppercase tracking-wider">{title}</span>
                <div className="text-2xl font-bold text-neutral-100">{value}</div>
                <div className="text-xs text-neutral-600 font-mono">{subtext}</div>
            </div>
        </div>
    </Link>
);

const QuickActionButton: React.FC<{ label: string; to: string }> = ({ label, to }) => (
    <Link to={to} className="flex items-center justify-between p-3 bg-neutral-900 border border-neutral-800 rounded hover:bg-neutral-800 transition-colors">
        <span className="text-neutral-300">{label}</span>
        <Settings className="w-4 h-4 text-neutral-600" />
    </Link>
)

export default AdminDashboard;
