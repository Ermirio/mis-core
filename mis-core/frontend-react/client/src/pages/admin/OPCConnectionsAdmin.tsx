import React, { useEffect, useState } from "react";
import { Plus, Wifi, WifiOff, RefreshCw, Settings, CheckCircle, XCircle } from "lucide-react";
import AdminDataGrid from "../../components/admin/AdminDataGrid";
import { Button } from "../../components/ui/button";
import { toast } from "sonner";

interface OPCConnection {
  id: number;
  nome: string;
  url_servidor: string;
  tag_monitoramento?: string;
  tipo_monitoramento: string;
  namespace_prefix: string;
  timeout: number;
  ativa: boolean;
  status_conexao?: 'CONNECTED' | 'DISCONNECTED' | 'ERROR';
  ultima_atualizacao?: string;
  latencia?: number;
}

const OPCConnectionsAdmin: React.FC = () => {
  const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";

  const [connections, setConnections] = useState<OPCConnection[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchConnections = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${DJANGO_API_URL}/conexoes-opc/`);
      const data = await resp.json();
      const conns = data.results || data;

      // Simular status de conexão (em produção, viria de um endpoint de health check)
      const connectionsWithStatus = conns.map((conn: any) => ({
        ...conn,
        status_conexao: conn.ativa ? 'CONNECTED' : 'DISCONNECTED',
        ultima_atualizacao: new Date().toISOString(),
        latencia: Math.floor(Math.random() * 50) + 10
      }));

      setConnections(connectionsWithStatus);
    } catch (error) {
      console.error("Erro ao carregar conexões OPC", error);
      toast.error("Falha ao carregar conexões OPC");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConnections();
    const interval = setInterval(fetchConnections, 15000); // Atualizar a cada 15s
    return () => clearInterval(interval);
  }, []);

  const testConnection = async (connectionId: number) => {
    toast.info("Testando conexão...");
    
    // Simular teste de conexão
    setTimeout(() => {
      const success = Math.random() > 0.2; // 80% de sucesso
      if (success) {
        toast.success("Conexão estabelecida com sucesso!");
      } else {
        toast.error("Falha ao conectar. Verifique as configurações.");
      }
    }, 2000);
  };

  const columns = [
    { key: "id", header: "ID", width: "50px" },
    { 
      key: "nome", 
      header: "Nome da Conexão",
      render: (item: OPCConnection) => (
        <div>
          <p className="text-neutral-200 font-medium">{item.nome}</p>
          <p className="text-xs text-neutral-600 font-mono">{item.url_servidor}</p>
        </div>
      )
    },
    {
      key: "status_conexao",
      header: "Status",
      render: (item: OPCConnection) => {
        const statusConfig = {
          CONNECTED: {
            icon: <Wifi className="w-4 h-4" />,
            color: 'text-emerald-400',
            bg: 'bg-emerald-500/10',
            border: 'border-emerald-500',
            label: 'Conectado'
          },
          DISCONNECTED: {
            icon: <WifiOff className="w-4 h-4" />,
            color: 'text-neutral-400',
            bg: 'bg-neutral-500/10',
            border: 'border-neutral-500',
            label: 'Desconectado'
          },
          ERROR: {
            icon: <XCircle className="w-4 h-4" />,
            color: 'text-red-400',
            bg: 'bg-red-500/10',
            border: 'border-red-500',
            label: 'Erro'
          }
        };

        const config = statusConfig[item.status_conexao || 'DISCONNECTED'];

        return (
          <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-md border ${config.bg} ${config.border} ${config.color}`}>
            {config.icon}
            <span className="text-xs font-medium uppercase">{config.label}</span>
          </div>
        );
      }
    },
    {
      key: "latencia",
      header: "Latência",
      render: (item: OPCConnection) => (
        <span className="text-emerald-400 font-mono">
          {item.latencia ? `${item.latencia}ms` : 'N/A'}
        </span>
      )
    },
    {
      key: "tipo_monitoramento",
      header: "Tipo Monitoramento",
      render: (item: OPCConnection) => (
        <span className="px-2 py-0.5 rounded text-xs bg-neutral-800 border border-neutral-700 text-neutral-300">
          {item.tipo_monitoramento}
        </span>
      )
    },
    {
      key: "timeout",
      header: "Timeout",
      render: (item: OPCConnection) => (
        <span className="text-neutral-400 font-mono">{item.timeout}s</span>
      )
    },
    {
      key: "ativa",
      header: "Ativa",
      render: (item: OPCConnection) => (
        item.ativa ? (
          <CheckCircle className="w-5 h-5 text-emerald-500" />
        ) : (
          <XCircle className="w-5 h-5 text-neutral-600" />
        )
      )
    },
    {
      key: "actions",
      header: "Ações",
      width: "120px",
      render: (item: OPCConnection) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-neutral-400 hover:text-emerald-400 hover:bg-emerald-950/30"
            onClick={() => testConnection(item.id)}
            title="Testar Conexão"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-neutral-400 hover:text-white hover:bg-neutral-800"
            title="Configurar"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      )
    }
  ];

  return (
    <div className="h-full flex flex-col space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-semibold text-neutral-100">Conexões OPC UA</h2>
          <p className="text-sm text-neutral-500">Gerenciar servidores OPC e monitorar saúde das conexões</p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={fetchConnections}
            variant="outline"
            className="bg-transparent border-neutral-700 text-neutral-300 hover:bg-neutral-800"
          >
            <RefreshCw className="mr-2 h-4 w-4" /> Atualizar
          </Button>
          <Button
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <Plus className="mr-2 h-4 w-4" /> Nova Conexão
          </Button>
        </div>
      </div>

      {/* Cards de Resumo */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Total</p>
              <p className="text-2xl font-bold text-neutral-200">{connections.length}</p>
            </div>
            <Settings className="w-8 h-8 text-neutral-600" />
          </div>
        </div>

        <div className="bg-neutral-950 border border-emerald-800/50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Conectadas</p>
              <p className="text-2xl font-bold text-emerald-400">
                {connections.filter(c => c.status_conexao === 'CONNECTED').length}
              </p>
            </div>
            <Wifi className="w-8 h-8 text-emerald-500" />
          </div>
        </div>

        <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Desconectadas</p>
              <p className="text-2xl font-bold text-neutral-400">
                {connections.filter(c => c.status_conexao === 'DISCONNECTED').length}
              </p>
            </div>
            <WifiOff className="w-8 h-8 text-neutral-600" />
          </div>
        </div>

        <div className="bg-neutral-950 border border-red-800/50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Com Erro</p>
              <p className="text-2xl font-bold text-red-400">
                {connections.filter(c => c.status_conexao === 'ERROR').length}
              </p>
            </div>
            <XCircle className="w-8 h-8 text-red-500" />
          </div>
        </div>
      </div>

      {/* DataGrid */}
      <div className="flex-1 min-h-0">
        <AdminDataGrid
          columns={columns}
          data={connections}
          loading={loading}
          onRowClick={(item) => {
            console.log("Conexão selecionada:", item);
          }}
        />
      </div>
    </div>
  );
};

export default OPCConnectionsAdmin;
