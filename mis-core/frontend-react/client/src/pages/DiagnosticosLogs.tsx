import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ArrowLeft,
  Download,
  Trash2,
  Eye,
  EyeOff
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://127.0.0.1:8000/api';
const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || 'http://127.0.0.1:5000/api';

interface EquipamentoStatus {
  codigo: string;
  nome: string;
  linha: string;
  status: 'online' | 'offline' | 'erro';
  ultima_leitura: string;
  campos_presentes: string[];
  campos_faltando: string[];
  dados_amostra: Record<string, any>;
  erros: string[];
}

interface DiagnosticoFluxo {
  timestamp: string;
  equipamento: string;
  etapa: 'coletor' | 'flask' | 'django' | 'frontend';
  status: 'sucesso' | 'erro' | 'aviso';
  mensagem: string;
  detalhes: Record<string, any>;
}

interface SystemHealth {
  influxdb: boolean;
  django: boolean;
  coletor: boolean;
  details: Record<string, string>;
}

const DiagnosticosLogs: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('fluxo');
  const [equipamentos, setEquipamentos] = useState<EquipamentoStatus[]>([]);
  const [logs, setLogs] = useState<DiagnosticoFluxo[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);

  const carregarDados = async () => {
    try {
      setLoading(true);
      const newLogs: DiagnosticoFluxo[] = [];

      // 1. Verificar Saúde do Sistema
      let healthData: SystemHealth | null = null;
      try {
        const healthResp = await fetch(`${FLASK_API_URL}/health/system`);
        if (healthResp.ok) {
          healthData = await healthResp.json();
          setSystemHealth(healthData);
        }
      } catch (e) {
        console.error("Erro check health:", e);
        setSystemHealth({ influxdb: false, django: false, coletor: false, details: { error: "Flask Unreachable" } });
        newLogs.push({
          timestamp: new Date().toISOString(),
          equipamento: 'SYSTEM',
          etapa: 'flask',
          status: 'erro',
          mensagem: 'Falha ao conectar Backend Flask',
          detalhes: { error: String(e) }
        });
      }

      if (healthData) {
        if (!healthData.influxdb) {
          newLogs.push({
            timestamp: new Date().toISOString(),
            equipamento: 'SYSTEM',
            etapa: 'flask',
            status: 'erro',
            mensagem: 'InfluxDB desconectado',
            detalhes: healthData.details
          });
        }
        if (!healthData.coletor) {
          newLogs.push({
            timestamp: new Date().toISOString(),
            equipamento: 'SYSTEM',
            etapa: 'coletor',
            status: 'erro',
            mensagem: 'Coletor não envia dados há 30s',
            detalhes: healthData.details
          });
        }
      }

      // 2. Buscar Dados Realtime de TODOS equipamentos
      try {
        const realtimeResp = await fetch(`${FLASK_API_URL}/realtime/all`);
        if (realtimeResp.ok) {
          const realtimeData = await realtimeResp.json();
          // Processar equipamentos
          const listaEquipamentos: EquipamentoStatus[] = [];

          Object.entries(realtimeData).forEach(([eqCode, data]: [string, any]) => {
            const medicoes = data.medicoes || {};
            const missingFields = [];
            const presentFields = Object.keys(medicoes).filter(k => medicoes[k] !== null && medicoes[k] !== undefined && medicoes[k] !== 'N/A');

            // Campos obrigatórios básicos
            if (!medicoes.estado_maquina) missingFields.push('estado_maquina');
            if (!medicoes.velocidade_atual && medicoes.velocidade_atual !== 0) missingFields.push('velocidade_atual');
            if (!medicoes.sku_codigo || medicoes.sku_codigo === 'N/A') missingFields.push('sku_codigo');

            const isOnline = presentFields.length > 5; // Heurística simples

            listaEquipamentos.push({
              codigo: eqCode,
              nome: data.descricao || eqCode,
              linha: 'N/A', // Poderia buscar do Django se precisasse
              status: isOnline ? 'online' : 'erro',
              ultima_leitura: data.timestamp,
              campos_presentes: presentFields,
              campos_faltando: missingFields,
              dados_amostra: medicoes,
              erros: missingFields.length > 0 ? [`Campos faltando: ${missingFields.join(', ')}`] : []
            });

            if (missingFields.length > 0) {
              newLogs.push({
                timestamp: new Date().toISOString(),
                equipamento: eqCode,
                etapa: 'coletor',
                status: 'aviso',
                mensagem: `Campos ausentes: ${missingFields.join(', ')}`,
                detalhes: { missing: missingFields }
              });
            }
          });
          setEquipamentos(listaEquipamentos);
        }
      } catch (e) {
        console.error("Erro fetch realtime:", e);
      }

      setLogs(prev => [...newLogs, ...prev].slice(0, 100)); // Manter ultimos 100 logs

    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarDados();
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(carregarDados, 10000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Voltar
          </Button>
          <h1 className="text-2xl font-bold">Diagnóstico do Sistema</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={autoRefresh ? "default" : "outline"}
            onClick={() => setAutoRefresh(!autoRefresh)}
            size="sm"
          >
            {autoRefresh ? <Eye className="w-4 h-4 mr-2" /> : <EyeOff className="w-4 h-4 mr-2" />}
            {autoRefresh ? "Auto (10s)" : "Pausado"}
          </Button>
          <Button variant="outline" size="sm" onClick={carregarDados} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="fluxo">Fluxo de Dados</TabsTrigger>
          <TabsTrigger value="status">Status dos Equipamentos</TabsTrigger>
          <TabsTrigger value="logs">Logs de Erro</TabsTrigger>
        </TabsList>

        <TabsContent value="fluxo" className="space-y-4">
          {/* Card Explicativo do Fluxo */}
          <Card>
            <CardHeader>
              <CardTitle>Fluxo de Dados</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg overflow-x-auto">
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mb-2">
                    <span className="text-2xl">🏭</span>
                  </div>
                  <span className="font-bold text-sm">CLP/Equipamento</span>
                  <span className="text-xs text-gray-500">OPC UA / Modbus</span>
                </div>

                <div className="h-0.5 w-16 bg-gray-300 relative">
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 text-xs text-gray-500">Leitura</div>
                </div>

                <div className="flex flex-col items-center">
                  <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-2 ${systemHealth?.coletor ? 'bg-green-100' : 'bg-red-100'}`}>
                    <span className="text-2xl">📡</span>
                  </div>
                  <span className="font-bold text-sm">Coletor Python</span>
                  <span className="text-xs text-gray-500">coletor.py</span>
                </div>

                <div className="h-0.5 w-16 bg-gray-300 relative">
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 text-xs text-gray-500">JSON</div>
                </div>

                <div className="flex flex-col items-center">
                  <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-2 ${systemHealth?.influxdb ? 'bg-green-100' : 'bg-red-100'}`}>
                    <span className="text-2xl">💾</span>
                  </div>
                  <span className="font-bold text-sm">InfluxDB</span>
                  <span className="text-xs text-gray-500">Série Temporal</span>
                </div>

                <div className="h-0.5 w-16 bg-gray-300 relative">
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 text-xs text-gray-500">Query</div>
                </div>

                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-full bg-purple-100 flex items-center justify-center mb-2">
                    <span className="text-2xl">🖥️</span>
                  </div>
                  <span className="font-bold text-sm">Frontend</span>
                  <span className="text-xs text-gray-500">React + Flask</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Checklist de Verificação Dinâmico */}
          <Card>
            <CardHeader>
              <CardTitle>Checklist de Saúde do Sistema</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {[
                { item: 'Flask API Online (Ping)', check: systemHealth ? '✓' : '❌', status: !!systemHealth },
                { item: 'Django API Acessível (Via Flask)', check: systemHealth?.django ? '✓' : '❌', status: systemHealth?.django },
                { item: 'InfluxDB Conectado', check: systemHealth?.influxdb ? '✓' : '❌', status: systemHealth?.influxdb },
                { item: 'Coletor Enviando Dados (Heartbeat)', check: systemHealth?.coletor ? '✓' : '❌', status: systemHealth?.coletor },
              ].map((item, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  <div className={`w-4 h-4 flex items-center justify-center rounded-full text-xs font-bold ${item.status ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {item.check}
                  </div>
                  <label className={`text-gray-700 ${!item.status ? 'font-semibold text-red-600' : ''}`}>
                    {item.item}
                  </label>
                </div>
              ))}

              {systemHealth?.details && Object.keys(systemHealth.details).length > 0 && (
                <div className="mt-4 p-2 bg-red-50 text-red-700 text-xs rounded">
                  <strong>Detalhes de Erro:</strong>
                  <pre>{JSON.stringify(systemHealth.details, null, 2)}</pre>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="status">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {equipamentos.map(eq => (
              <Card key={eq.codigo}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-bold flex justify-between">
                    {eq.nome} ({eq.codigo})
                    <Badge variant={eq.status === 'online' ? 'default' : 'destructive'}>
                      {eq.status.toUpperCase()}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-xs space-y-1">
                    <p><strong>Última Leitura:</strong> {new Date(eq.ultima_leitura).toLocaleString()}</p>
                    <p><strong>Campos Presentes:</strong> {eq.campos_presentes.length}</p>
                    <p><strong>Campos Faltando:</strong> {eq.campos_faltando.length}</p>
                    {eq.erros.length > 0 && (
                      <div className="text-red-600 mt-2">
                        {eq.erros.map((e, i) => <div key={i}>{e}</div>)}
                      </div>
                    )}
                    <div className="mt-2 bg-slate-100 p-2 rounded max-h-32 overflow-auto">
                      <pre>{JSON.stringify(eq.dados_amostra, null, 2)}</pre>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {equipamentos.length === 0 && <div className="text-center p-8 text-gray-500">Nenhum equipamento encontrado.</div>}
          </div>
        </TabsContent>

        <TabsContent value="logs">
          <Card>
            <CardHeader>
              <CardTitle>Logs do Sistema</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {logs.map((log, i) => (
                  <Alert key={i} variant={log.status === 'erro' ? 'destructive' : 'default'}>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription className="flex justify-between items-center w-full">
                      <span>
                        <strong>[{new Date(log.timestamp).toLocaleTimeString()}]</strong> [{log.equipamento}] {log.mensagem}
                      </span>
                    </AlertDescription>
                  </Alert>
                ))}
                {logs.length === 0 && <div className="text-center p-4 text-gray-500">Nenhum erro registrado recentemente.</div>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DiagnosticosLogs;
