import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertTriangle, TrendingUp, Clock, Target } from 'lucide-react';

interface VazaoData {
  periodo: 'TURNO' | 'DIA' | 'SEMANA' | 'MÊS';
  turno?: string;
  turno_codigo?: string;
  data: string;
  planejado: number;
  produzido: number;
  falta_produzir: number;
  horas_restantes: number;
  vazao_necessaria: number;
  meta_vazao: number;
  status: 'OK' | 'CRÍTICO';
}

interface LinhaVazao {
  linha_id: number;
  linha_codigo: string;
  linha_nome: string;
  turno: VazaoData;
  dia: VazaoData;
  semana: VazaoData;
  mes: VazaoData;
}

interface DashboardData {
  status: string;
  timestamp: string;
  total_linhas: number;
  alertas_criticos: number;
  linhas: LinhaVazao[];
  alertas: Array<{
    linha_id: number;
    linha_codigo: string;
    linha_nome: string;
    periodo: string;
    vazao_necessaria: number;
    meta_vazao: number;
    falta_produzir: number;
    horas_restantes: number;
  }>;
}

const FactoryManagement: React.FC = () => {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPeriodo, setSelectedPeriodo] = useState<'TURNO' | 'DIA' | 'SEMANA' | 'MÊS'>('TURNO');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://localhost:8000/api';

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/dashboard/factory-manage/`);
      if (response.ok) {
        const data = await response.json();
        setDashboardData(data);
      } else {
        setError('Erro ao buscar dados do dashboard');
      }
    } catch (err) {
      console.error('Erro ao buscar dashboard:', err);
      setError('Erro de conexão com o servidor');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();

    // Auto-refresh a cada 30 segundos se habilitado
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(fetchDashboardData, 30000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const getStatusColor = (status: 'OK' | 'CRÍTICO') => {
    return status === 'OK' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800';
  };

  const getStatusIcon = (status: 'OK' | 'CRÍTICO') => {
    return status === 'OK' ? '✓' : '⚠';
  };

  const getPeriodoLabel = (periodo: string) => {
    const labels: Record<string, string> = {
      TURNO: 'Turno',
      DIA: 'Dia',
      SEMANA: 'Semana',
      MÊS: 'Mês'
    };
    return labels[periodo] || periodo;
  };

  const getVazaoData = (linha: LinhaVazao): VazaoData => {
    const periodoMap: Record<string, VazaoData> = {
      TURNO: linha.turno,
      DIA: linha.dia,
      SEMANA: linha.semana,
      MÊS: linha.mes
    };
    return periodoMap[selectedPeriodo];
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-lg text-gray-500">Carregando dados...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Gestão da Fábrica - Vazão Necessária</h1>
          <p className="text-gray-500 text-sm mt-1">
            Última atualização: {dashboardData?.timestamp ? new Date(dashboardData.timestamp).toLocaleTimeString('pt-BR') : 'N/A'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={autoRefresh ? 'default' : 'outline'}
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            {autoRefresh ? 'Auto-atualização ON' : 'Auto-atualização OFF'}
          </Button>
          <Button onClick={fetchDashboardData}>Atualizar Agora</Button>
        </div>
      </div>

      {/* Alertas Críticos */}
      {dashboardData && dashboardData.alertas_criticos > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <strong>{dashboardData.alertas_criticos} alerta(s) crítico(s)</strong> - Vazão necessária acima da meta em algumas linhas
          </AlertDescription>
        </Alert>
      )}

      {/* Seletor de Período */}
      <Card>
        <CardHeader>
          <CardTitle>Seletor de Período</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {(['TURNO', 'DIA', 'SEMANA', 'MÊS'] as const).map((periodo) => (
              <Button
                key={periodo}
                variant={selectedPeriodo === periodo ? 'default' : 'outline'}
                onClick={() => setSelectedPeriodo(periodo)}
              >
                {getPeriodoLabel(periodo)}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Resumo de Alertas */}
      {dashboardData && dashboardData.alertas.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Alertas Críticos</CardTitle>
            <CardDescription>Linhas que precisam aumentar a vazão para cumprir o plano</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {dashboardData.alertas.map((alerta, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded">
                  <div>
                    <p className="font-semibold">{alerta.linha_nome} ({alerta.linha_codigo})</p>
                    <p className="text-sm text-gray-600">
                      {alerta.periodo}: Vazão necessária de {alerta.vazao_necessaria.toFixed(2)} ton/h (meta: {alerta.meta_vazao.toFixed(2)} ton/h)
                    </p>
                    <p className="text-sm text-gray-600">
                      Falta produzir: {alerta.falta_produzir.toFixed(0)} unidades em {alerta.horas_restantes.toFixed(1)}h
                    </p>
                  </div>
                  <Badge variant="destructive">CRÍTICO</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabela Principal de Linhas */}
      <Card>
        <CardHeader>
          <CardTitle>Linhas de Produção - {getPeriodoLabel(selectedPeriodo)}</CardTitle>
          <CardDescription>
            {dashboardData?.total_linhas} linha(s) ativa(s)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Linha</TableHead>
                  <TableHead className="text-right">Planejado</TableHead>
                  <TableHead className="text-right">Produzido</TableHead>
                  <TableHead className="text-right">Falta Produzir</TableHead>
                  <TableHead className="text-right">Horas Restantes</TableHead>
                  <TableHead className="text-right">Vazão Necessária</TableHead>
                  <TableHead className="text-right">Meta Vazão</TableHead>
                  <TableHead className="text-center">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dashboardData?.linhas.map((linha) => {
                  const vazaoData = getVazaoData(linha);
                  return (
                    <TableRow key={linha.linha_id}>
                      <TableCell className="font-semibold">
                        {linha.linha_nome}
                        <br />
                        <span className="text-xs text-gray-500">{linha.linha_codigo}</span>
                      </TableCell>
                      <TableCell className="text-right">{vazaoData.planejado}</TableCell>
                      <TableCell className="text-right">{vazaoData.produzido.toFixed(0)}</TableCell>
                      <TableCell className="text-right font-semibold">{vazaoData.falta_produzir.toFixed(0)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Clock className="w-4 h-4 text-gray-400" />
                          {vazaoData.horas_restantes.toFixed(1)}h
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <TrendingUp className="w-4 h-4 text-blue-500" />
                          <span className="font-semibold">{vazaoData.vazao_necessaria.toFixed(2)}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Target className="w-4 h-4 text-green-500" />
                          {vazaoData.meta_vazao.toFixed(2)}
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge className={getStatusColor(vazaoData.status)}>
                          {getStatusIcon(vazaoData.status)} {vazaoData.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Detalhes por Turno (se aplicável) */}
      {selectedPeriodo === 'TURNO' && dashboardData?.linhas && (
        <Card>
          <CardHeader>
            <CardTitle>Informações do Turno</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {dashboardData.linhas.map((linha) => (
                <div key={linha.linha_id} className="p-3 border rounded">
                  <p className="font-semibold mb-2">{linha.linha_nome}</p>
                  <div className="text-sm space-y-1">
                    <p>Turno: <span className="font-medium">{linha.turno.turno}</span></p>
                    <p>Data: <span className="font-medium">{new Date(linha.turno.data).toLocaleDateString('pt-BR')}</span></p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Rodapé com Legenda */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Legenda</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="font-semibold mb-1">Planejado</p>
              <p className="text-gray-600">Total de unidades planejadas para o período</p>
            </div>
            <div>
              <p className="font-semibold mb-1">Vazão Necessária</p>
              <p className="text-gray-600">(Planejado - Produzido) / Horas Restantes</p>
            </div>
            <div>
              <p className="font-semibold mb-1">Status</p>
              <p className="text-gray-600">OK: Vazão ≤ Meta | CRÍTICO: Vazão &gt; Meta</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default FactoryManagement;
