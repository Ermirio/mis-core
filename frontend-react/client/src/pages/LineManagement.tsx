import React, { useState, useEffect } from 'react';
import { ArrowLeft, RefreshCw, TrendingUp, AlertCircle, CheckCircle } from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';

interface EquipamentoStatus {
  equipamento: string;
  medicoes: {
    contagem_saida: number;
    contagem_entrada: number;
    velocidade_atual: number;
    descarte: number;
    percentual_descarte: number;
    formato_gramas: number;
    planejado_op: number;
    descricao: string;
    temperatura: number;
    pressao: number;
    oee: number;
    disponibilidade: number;
    performance: number;
    qualidade: number;
  };
}

interface LinhaStatusResponse {
  linha: string;
  timestamp: string;
  status: string;
  equipamentos: EquipamentoStatus[];
  agregados: {
    total_equipamentos: number;
    total_contagem_saida: number;
    total_descarte: number;
    media_oee: number;
    media_velocidade: number;
  };
}

const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://localhost:5000/api';

/**
 * LineManagement - Tela de Gerenciamento de Linha
 * 
 * Exibe status consolidado de uma linha de produção com dados reais do InfluxDB
 * - Status de todos os equipamentos
 * - Agregados da linha (OEE, velocidade, produção)
 * - Timeline de dados
 * - Alertas de problemas
 */
const LineManagement: React.FC = () => {
  const { linhaId } = useParams<{ linhaId: string }>();
  const navigate = useNavigate();
  
  const [linhaStatus, setLinhaStatus] = useState<LinhaStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Busca status da linha
  const fetchLinhaStatus = async () => {
    try {
      setError(null);
      const response = await fetch(`${FLASK_API_URL}/linha/${linhaId}/status`);
      
      if (!response.ok) {
        throw new Error(`Erro ao buscar status: ${response.statusText}`);
      }
      
      const data = await response.json();
      setLinhaStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      console.error('Erro ao buscar status da linha:', err);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh a cada 10 segundos
  useEffect(() => {
    fetchLinhaStatus();
    
    if (autoRefresh) {
      const interval = setInterval(fetchLinhaStatus, 10000);
      return () => clearInterval(interval);
    }
  }, [linhaId, autoRefresh]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando dados da linha...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-red-600" />
          <div>
            <h3 className="font-bold text-red-900">Erro ao carregar dados</h3>
            <p className="text-red-700">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!linhaStatus) {
    return (
      <div className="p-6 bg-yellow-50 border border-yellow-200 rounded-lg">
        <p className="text-yellow-900">Nenhum dado disponível para esta linha</p>
      </div>
    );
  }

  const { agregados, equipamentos } = linhaStatus;

  // Determina cor do OEE
  const getOEEColor = (valor: number): string => {
    if (valor >= 85) return 'bg-green-100 text-green-900';
    if (valor >= 70) return 'bg-yellow-100 text-yellow-900';
    return 'bg-red-100 text-red-900';
  };

  // Determina cor da velocidade
  const getVelocidadeColor = (valor: number, planejado: number): string => {
    const percentual = (valor / planejado) * 100;
    if (percentual >= 90) return 'text-green-600';
    if (percentual >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/home')}
            className="p-2 hover:bg-gray-200 rounded-lg transition"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Gerenciamento de Linha</h1>
            <p className="text-gray-600">Linha: {linhaId}</p>
          </div>
        </div>
        
        <button
          onClick={fetchLinhaStatus}
          className="p-2 hover:bg-gray-200 rounded-lg transition"
          title="Atualizar dados"
        >
          <RefreshCw className="w-6 h-6" />
        </button>
      </div>

      {/* Auto-refresh toggle */}
      <div className="mb-6 flex items-center gap-2">
        <input
          type="checkbox"
          id="autoRefresh"
          checked={autoRefresh}
          onChange={(e) => setAutoRefresh(e.target.checked)}
          className="w-4 h-4"
        />
        <label htmlFor="autoRefresh" className="text-sm text-gray-600">
          Auto-atualizar a cada 10 segundos
        </label>
      </div>

      {/* Agregados da Linha */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
        {/* Total de Equipamentos */}
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-gray-600 mb-2">Equipamentos Online</p>
          <p className="text-3xl font-bold text-blue-600">{agregados.total_equipamentos}</p>
        </div>

        {/* Produção Total */}
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-gray-600 mb-2">Peças Produzidas</p>
          <p className="text-3xl font-bold text-green-600">{agregados.total_contagem_saida.toLocaleString()}</p>
        </div>

        {/* Descartes */}
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-gray-600 mb-2">Descartes</p>
          <p className="text-3xl font-bold text-red-600">{agregados.total_descarte}</p>
        </div>

        {/* OEE Médio */}
        <div className={`p-4 rounded-lg shadow ${getOEEColor(agregados.media_oee)}`}>
          <p className="text-sm mb-2 font-semibold">OEE Médio</p>
          <p className="text-3xl font-bold">{agregados.media_oee.toFixed(1)}%</p>
        </div>

        {/* Velocidade Média */}
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-gray-600 mb-2">Velocidade Média</p>
          <p className="text-3xl font-bold text-blue-600">{agregados.media_velocidade.toFixed(0)} un/min</p>
        </div>
      </div>

      {/* Equipamentos */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="bg-gray-100 p-4 border-b">
          <h2 className="text-lg font-bold text-gray-900">Status dos Equipamentos</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">Equipamento</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">Status</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-700">Produzidas</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-700">Descartes</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-700">Velocidade</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-700">OEE</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-700">Temp</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-700">Pressão</th>
              </tr>
            </thead>
            <tbody>
              {equipamentos.map((eq, idx) => (
                <tr key={idx} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-semibold text-gray-900">{eq.equipamento}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-900">
                      <CheckCircle className="w-4 h-4" />
                      ONLINE
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-900 font-semibold">
                    {eq.medicoes.contagem_saida.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-red-600 font-semibold">
                    {eq.medicoes.descarte}
                  </td>
                  <td className={`px-4 py-3 text-right font-semibold ${getVelocidadeColor(eq.medicoes.velocidade_atual, eq.medicoes.planejado_op)}`}>
                    {eq.medicoes.velocidade_atual} un/min
                  </td>
                  <td className={`px-4 py-3 text-right font-semibold ${getOEEColor(eq.medicoes.oee)}`}>
                    {eq.medicoes.oee.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {eq.medicoes.temperatura.toFixed(1)}°C
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {eq.medicoes.pressao.toFixed(2)} bar
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detalhes de Equipamentos */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {equipamentos.map((eq, idx) => (
          <div key={idx} className="bg-white rounded-lg shadow p-4">
            <h3 className="text-lg font-bold text-gray-900 mb-4">{eq.equipamento}</h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-600">Descrição</p>
                <p className="text-sm font-semibold text-gray-900">{eq.medicoes.descricao || 'N/A'}</p>
              </div>
              
              <div>
                <p className="text-xs text-gray-600">Formato</p>
                <p className="text-sm font-semibold text-gray-900">{eq.medicoes.formato_gramas}g</p>
              </div>
              
              <div>
                <p className="text-xs text-gray-600">Disponibilidade</p>
                <p className="text-sm font-semibold text-gray-900">{eq.medicoes.disponibilidade.toFixed(1)}%</p>
              </div>
              
              <div>
                <p className="text-xs text-gray-600">Performance</p>
                <p className="text-sm font-semibold text-gray-900">{eq.medicoes.performance.toFixed(1)}%</p>
              </div>
              
              <div>
                <p className="text-xs text-gray-600">Qualidade</p>
                <p className="text-sm font-semibold text-gray-900">{eq.medicoes.qualidade.toFixed(1)}%</p>
              </div>
              
              <div>
                <p className="text-xs text-gray-600">% Descarte</p>
                <p className="text-sm font-semibold text-red-600">{eq.medicoes.percentual_descarte.toFixed(2)}%</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Timestamp */}
      <div className="mt-6 text-center text-xs text-gray-500">
        Última atualização: {new Date(linhaStatus.timestamp).toLocaleString('pt-BR')}
      </div>
    </div>
  );
};

export default LineManagement;
