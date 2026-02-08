import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Settings, Database, Activity, Server, Cpu, TrendingUp, AlertTriangle, CheckCircle } from "lucide-react";
import OEEChart from "../../components/admin/OEEChart";
import EquipmentStateIndicator from "../../components/admin/EquipmentStateIndicator";
import useRealTimeData from "../../hooks/useRealTimeData";

interface SystemMetrics {
  total_equipamentos: number;
  equipamentos_offline: number;
  total_tags: number;
  taxa_ingestao: string;
  uptime_30d: number;
  oee_medio: number;
  disponibilidade: number;
  performance: number;
  qualidade: number;
}

interface EquipmentStatus {
  id: number;
  nome: string;
  codigo: string;
  estado: string;
  velocidade_atual: number;
  linha_nome: string;
}

const AdminDashboard: React.FC = () => {
  const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";
  const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || "http://127.0.0.1:5000/api";

  const [metrics, setMetrics] = useState<SystemMetrics>({
    total_equipamentos: 0,
    equipamentos_offline: 0,
    total_tags: 0,
    taxa_ingestao: "0 KB/s",
    uptime_30d: 0,
    oee_medio: 0,
    disponibilidade: 0,
    performance: 0,
    qualidade: 0
  });

  const [equipmentStatus, setEquipmentStatus] = useState<EquipmentStatus[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch de métricas do sistema
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        // Buscar equipamentos
        const equipResp = await fetch(`${DJANGO_API_URL}/equipamentos/`);
        const equipData = await equipResp.json();
        const equipamentos = equipData.results || equipData;

        // Buscar tags
        const tagsResp = await fetch(`${DJANGO_API_URL}/tags/`);
        const tagsData = await tagsResp.json();
        const tags = tagsData.results || tagsData;

        // Calcular métricas (simuladas para demonstração)
        const totalEquip = equipamentos.length;
        const offline = Math.floor(totalEquip * 0.15); // 15% offline

        // OEE médio simulado (em produção, viria do backend)
        const oeeData = {
          disponibilidade: 92.5,
          performance: 87.3,
          qualidade: 98.2,
          oee: 79.3
        };

        setMetrics({
          total_equipamentos: totalEquip,
          equipamentos_offline: offline,
          total_tags: tags.length,
          taxa_ingestao: `${(tags.length * 0.5).toFixed(1)} KB/s`,
          uptime_30d: 98.5,
          ...oeeData
        });

        // Status de equipamentos (primeiros 5)
        const statusData = equipamentos.slice(0, 5).map((eq: any) => ({
          id: eq.id,
          nome: eq.nome,
          codigo: eq.codigo,
          estado: 'RUN', // Em produção, viria do Flask API
          velocidade_atual: Math.random() * 100,
          linha_nome: eq.linha_nome || 'N/A'
        }));
        
        setEquipmentStatus(statusData);
        setLoading(false);
      } catch (error) {
        console.error("Erro ao carregar métricas", error);
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000); // Atualizar a cada 10s

    return () => clearInterval(interval);
  }, [DJANGO_API_URL]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-neutral-400">Carregando dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-neutral-100">Visão Geral do Sistema</h2>
          <p className="text-sm text-neutral-500 mt-1">Monitoramento em tempo real da planta industrial</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-neutral-600">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span>Atualização automática ativa</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <DashboardCard
          title="Equipamentos"
          value={metrics.total_equipamentos.toString()}
          subtext={`${metrics.equipamentos_offline} Offline`}
          icon={<Server className="w-6 h-6 text-emerald-500" />}
          link="/admin/equipamentos"
          trend={metrics.equipamentos_offline === 0 ? 'up' : 'down'}
        />
        <DashboardCard
          title="Tags OPC"
          value={metrics.total_tags.toLocaleString()}
          subtext={`${metrics.taxa_ingestao} Ingestion`}
          icon={<Activity className="w-6 h-6 text-blue-500" />}
          link="/admin/tags"
          trend="stable"
        />
        <DashboardCard
          title="OEE Médio"
          value={`${metrics.oee_medio.toFixed(1)}%`}
          subtext="Últimas 24h"
          icon={<TrendingUp className="w-6 h-6 text-purple-500" />}
          link="/admin/analytics"
          trend={metrics.oee_medio >= 85 ? 'up' : 'down'}
        />
        <DashboardCard
          title="Uptime"
          value={`${metrics.uptime_30d}%`}
          subtext="Últimos 30 dias"
          icon={<Cpu className="w-6 h-6 text-green-500" />}
          link="/diagnosticos"
          trend="up"
        />
      </div>

      {/* OEE Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <OEEChart
          data={{
            disponibilidade: metrics.disponibilidade,
            performance: metrics.performance,
            qualidade: metrics.qualidade,
            oee: metrics.oee_medio
          }}
          meta={85}
          title="OEE Geral da Planta"
          showBreakdown={true}
        />

        {/* Status de Equipamentos */}
        <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-neutral-200 mb-4">Status de Equipamentos</h3>
          <div className="space-y-3">
            {equipmentStatus.map((eq) => (
              <div
                key={eq.id}
                className="flex items-center justify-between p-3 bg-neutral-900 border border-neutral-800 rounded-lg hover:border-emerald-500/50 transition-colors"
              >
                <div className="flex-1">
                  <p className="text-sm font-medium text-neutral-200">{eq.nome}</p>
                  <p className="text-xs text-neutral-500 font-mono">{eq.codigo} - {eq.linha_nome}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-xs text-neutral-500">Velocidade</p>
                    <p className="text-sm font-mono text-emerald-400">{eq.velocidade_atual.toFixed(1)} u/min</p>
                  </div>
                  <EquipmentStateIndicator
                    state={eq.estado as any}
                    size="sm"
                    showLabel={false}
                  />
                </div>
              </div>
            ))}
          </div>
          <Link
            to="/admin/equipamentos"
            className="block mt-4 text-center text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            Ver todos os equipamentos →
          </Link>
        </div>
      </div>

      {/* Ações Rápidas e Diagnóstico */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6">
          <h3 className="text-lg font-medium text-neutral-300 mb-4">Ações Rápidas</h3>
          <div className="space-y-3">
            <QuickActionButton label="Gerenciar Equipamentos" to="/admin/equipamentos" icon={<Server className="w-4 h-4" />} />
            <QuickActionButton label="Planejamento de Produção" to="/admin/ordens" icon={<Activity className="w-4 h-4" />} />
            <QuickActionButton label="Catálogo de Produtos" to="/admin/produtos" icon={<Database className="w-4 h-4" />} />
            <QuickActionButton label="Configurar Tags OPC" to="/admin/tags" icon={<Settings className="w-4 h-4" />} />
            <QuickActionButton label="Ver Logs de Erro" to="/diagnosticos" icon={<AlertTriangle className="w-4 h-4" />} />
          </div>
        </div>

        <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6">
          <h3 className="text-lg font-medium text-neutral-300 mb-4">Diagnóstico Rápido</h3>
          <div className="space-y-4 text-sm">
            <DiagnosticItem label="API Latency" value="45ms" status="good" />
            <DiagnosticItem label="OPC Collector Status" value="CONNECTED" status="good" />
            <DiagnosticItem label="InfluxDB Health" value="Healthy (15ms)" status="good" />
            <DiagnosticItem label="PostgreSQL Status" value="Online" status="good" />
            <DiagnosticItem label="Last Backup" value="2 hours ago" status="warning" />
            <DiagnosticItem label="Disk Usage" value="67%" status="good" />
          </div>
        </div>
      </div>
    </div>
  );
};

interface DashboardCardProps {
  title: string;
  value: string;
  subtext: string;
  icon: React.ReactNode;
  link: string;
  trend?: 'up' | 'down' | 'stable';
}

const DashboardCard: React.FC<DashboardCardProps> = ({ title, value, subtext, icon, link, trend = 'stable' }) => {
  const trendColors = {
    up: 'bg-emerald-500',
    down: 'bg-red-500',
    stable: 'bg-blue-500'
  };

  return (
    <Link to={link} className="block group">
      <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6 hover:border-emerald-500/50 transition-all duration-200 hover:shadow-lg hover:shadow-emerald-500/10">
        <div className="flex justify-between items-start mb-4">
          <div className="p-2 bg-neutral-900 rounded-md border border-neutral-800 group-hover:border-neutral-700 transition-colors">
            {icon}
          </div>
          <div className={`w-2 h-2 rounded-full animate-pulse ${trendColors[trend]}`}></div>
        </div>
        <div className="space-y-1">
          <span className="text-sm font-medium text-neutral-500 uppercase tracking-wider">{title}</span>
          <div className="text-2xl font-bold text-neutral-100">{value}</div>
          <div className="text-xs text-neutral-600 font-mono">{subtext}</div>
        </div>
      </div>
    </Link>
  );
};

interface QuickActionButtonProps {
  label: string;
  to: string;
  icon: React.ReactNode;
}

const QuickActionButton: React.FC<QuickActionButtonProps> = ({ label, to, icon }) => (
  <Link to={to} className="flex items-center justify-between p-3 bg-neutral-900 border border-neutral-800 rounded hover:bg-neutral-800 hover:border-emerald-500/50 transition-all">
    <span className="text-neutral-300">{label}</span>
    <div className="text-neutral-600 group-hover:text-emerald-400 transition-colors">
      {icon}
    </div>
  </Link>
);

interface DiagnosticItemProps {
  label: string;
  value: string;
  status: 'good' | 'warning' | 'error';
}

const DiagnosticItem: React.FC<DiagnosticItemProps> = ({ label, value, status }) => {
  const statusConfig = {
    good: { color: 'text-emerald-400', icon: <CheckCircle className="w-4 h-4" /> },
    warning: { color: 'text-amber-400', icon: <AlertTriangle className="w-4 h-4" /> },
    error: { color: 'text-red-400', icon: <AlertTriangle className="w-4 h-4" /> }
  };

  const config = statusConfig[status];

  return (
    <div className="flex justify-between items-center border-b border-neutral-800 pb-2">
      <span className="text-neutral-400">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`font-mono ${config.color}`}>{value}</span>
        <div className={config.color}>
          {config.icon}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
