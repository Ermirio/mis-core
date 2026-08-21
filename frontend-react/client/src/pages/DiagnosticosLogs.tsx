import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ArrowLeft,
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Panel, Tag, AlertList, type AlertItem } from '@/components/v2';

import { DJANGO_API_URL, FLASK_API_URL } from '@/config/api';
import { MOCK_SYSTEM_HEALTH, MOCK_REALTIME_ALL } from '@/mocks/demoData';

interface EquipamentoStatus {
  codigo: string;
  nome: string;
  linha: string;
  linha_codigo?: string;
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

  const equipamentosPorLinha = useMemo(() => {
    return equipamentos.reduce((acc: Record<string, EquipamentoStatus[]>, eq) => {
      const key = eq.linha || 'Sem linha';
      if (!acc[key]) acc[key] = [];
      acc[key].push(eq);
      return acc;
    }, {});
  }, [equipamentos]);

  const carregarDados = async () => {
    try {
      setLoading(true);
      const newLogs: DiagnosticoFluxo[] = [];

      // 1. Verificar Saúde do Sistema
      let healthData: SystemHealth | null = null;
      try {
        // Flask-out Onda 1: /health/system migrado para Django.
        const healthResp = await fetch(`${DJANGO_API_URL}/health/system`);
        if (healthResp.ok) {
          healthData = await healthResp.json();
          setSystemHealth(healthData);
        }
      } catch (e) {
        console.error("Erro check health:", e);
        setSystemHealth(null);
        healthData = null;
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
        // Flask-out Onda 1: /realtime/all migrado para Django.
        const realtimeResp = await fetch(`${DJANGO_API_URL}/realtime/all`);
        if (realtimeResp.ok) {
          const realtimeData = await realtimeResp.json();
          const equipamentosResp = await fetch(`${DJANGO_API_URL}/equipamentos/?page_size=10000`);
          const equipamentosData = equipamentosResp.ok ? await equipamentosResp.json() : [];
          const equipamentosConfig = Array.isArray(equipamentosData?.results)
            ? equipamentosData.results
            : Array.isArray(equipamentosData)
              ? equipamentosData
              : [];
          const equipamentosByCode = equipamentosConfig.reduce((acc: Record<string, any>, eq: any) => {
            if (eq?.codigo) acc[eq.codigo] = eq;
            return acc;
          }, {});
          // Processar equipamentos
          const listaEquipamentos: EquipamentoStatus[] = [];

          Object.entries(realtimeData).forEach(([eqCode, data]: [string, any]) => {
            const config = equipamentosByCode[eqCode];
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
              nome: config?.nome || data.descricao || eqCode,
              linha: config?.linha_nome || config?.linha_codigo || 'Sem linha',
              linha_codigo: config?.linha_codigo,
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
          equipamentosConfig
            .filter((eq: any) => eq?.codigo && !realtimeData[eq.codigo])
            .forEach((eq: any) => {
              listaEquipamentos.push({
                codigo: eq.codigo,
                nome: eq.nome || eq.codigo,
                linha: eq.linha_nome || eq.linha_codigo || 'Sem linha',
                linha_codigo: eq.linha_codigo,
                status: 'offline',
                ultima_leitura: new Date().toISOString(),
                campos_presentes: [],
                campos_faltando: ['estado_maquina', 'velocidade_atual', 'sku_codigo'],
                dados_amostra: {
                  status_cadastro: eq.status,
                  tags_coleta: eq.tags_coleta?.map((tag: any) => tag.nome_metrica) || [],
                },
                erros: ['Equipamento cadastrado sem leitura recente em /realtime/all'],
              });
              newLogs.push({
                timestamp: new Date().toISOString(),
                equipamento: eq.codigo,
                etapa: 'coletor',
                status: 'aviso',
                mensagem: 'Equipamento cadastrado sem amostra recente em /realtime/all',
                detalhes: { linha: eq.linha_nome, codigo: eq.codigo, nome: eq.nome }
              });
            });

          listaEquipamentos.sort((a, b) => `${a.linha}${a.codigo}`.localeCompare(`${b.linha}${b.codigo}`));
          setEquipamentos(listaEquipamentos);
        }
      } catch (e) {
        console.error("Erro fetch realtime:", e);
        // Sem fallback de mock — equipamentos vazio em produção/erro.
        setEquipamentos([]);
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

  // Converte logs internos pra AlertItem (mesmo formato da POC)
  const logsAsAlerts: AlertItem[] = logs.map(l => ({
    time: new Date(l.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    sev: l.status === 'erro' ? 'bad' : l.status === 'aviso' ? 'warn' : 'ok',
    msg: <><b>[{l.equipamento}]</b> {l.mensagem}</>,
    ctx: <code style={{ fontFamily: 'var(--isa-mono)', fontSize: 'var(--isa-fs-meta)' }}>{l.etapa.toUpperCase()}</code>,
  }));

  return (
    <div className="isa-root" style={{ padding: '16px 20px', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Topbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <button
            type="button"
            onClick={() => navigate('/')}
            style={{ background: 'transparent', border: 0, color: 'var(--isa-text-muted)', cursor: 'pointer', fontSize: 'var(--isa-fs-body)', display: 'flex', alignItems: 'center', gap: 4, padding: '4px 0', marginBottom: 4 }}
          >
            <ArrowLeft size={14} /> Voltar
          </button>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--isa-text)' }}>Diagnóstico do Sistema</h1>
          <div style={{ marginTop: 2, fontSize: 'var(--isa-fs-default)', color: 'var(--isa-text-muted)' }}>
            Saúde do pipeline OPC → Coletor → InfluxDB → API → Frontend
          </div>
        </div>
        <div className="isa-toolbar" style={{ marginBottom: 0 }}>
          <label className="isa-switch">
            <input type="checkbox" checked={autoRefresh} onChange={() => setAutoRefresh(!autoRefresh)} />
            Auto-atualizar (10s)
          </label>
          <button type="button" onClick={carregarDados} disabled={loading}>
            <RefreshCw size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
            Atualizar
          </button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="fluxo">Fluxo de Dados</TabsTrigger>
          <TabsTrigger value="status">Status dos Equipamentos</TabsTrigger>
          <TabsTrigger value="logs">Logs de Erro</TabsTrigger>
        </TabsList>

        <TabsContent value="fluxo" className="space-y-4">
          {/* Diagrama do fluxo */}
          <Panel title="Fluxo de Dados">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 14, background: 'var(--isa-bg)', borderRadius: 'var(--isa-radius)', overflowX: 'auto', gap: 8 }}>
              <FluxoNode emoji="🏭" titulo="CLP/Equipamento" sub="OPC UA / Modbus" status="ok" />
              <Conector label="Leitura" />
              <FluxoNode emoji="📡" titulo="Coletor Python" sub="coletor.py" status={systemHealth?.coletor ? 'ok' : 'bad'} />
              <Conector label="JSON" />
              <FluxoNode emoji="💾" titulo="InfluxDB" sub="Série Temporal" status={systemHealth?.influxdb ? 'ok' : 'bad'} />
              <Conector label="Query" />
              <FluxoNode emoji="🖥️" titulo="Frontend" sub="React" status="ok" />
            </div>
          </Panel>

          {/* Checklist de saúde */}
          <Panel title="Checklist de Saúde do Sistema">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { item: 'Flask API Online (Ping)',          status: !!systemHealth },
                { item: 'Django API Acessível (Via Flask)', status: systemHealth?.django },
                { item: 'InfluxDB Conectado',               status: systemHealth?.influxdb },
                { item: 'Coletor Enviando Dados (Heartbeat)', status: systemHealth?.coletor },
              ].map((row, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--isa-fs-default)' }}>
                  {row.status
                    ? <CheckCircle size={16} style={{ color: 'var(--isa-ok)' }} />
                    : <XCircle size={16} style={{ color: 'var(--isa-bad)' }} />
                  }
                  <span style={{ color: row.status ? 'var(--isa-text)' : 'var(--isa-bad)', fontWeight: row.status ? 400 : 600 }}>
                    {row.item}
                  </span>
                </div>
              ))}

              {systemHealth?.details && Object.keys(systemHealth.details).length > 0 && (
                <pre style={{
                  marginTop: 8, padding: 10,
                  background: 'var(--isa-bad-bg)',
                  color: 'var(--isa-bad)',
                  fontSize: 'var(--isa-fs-meta)',
                  fontFamily: 'var(--isa-mono)',
                  borderRadius: 'var(--isa-radius)',
                  whiteSpace: 'pre-wrap',
                }}>
                  <strong>Detalhes de Erro:</strong>{'\n'}{JSON.stringify(systemHealth.details, null, 2)}
                </pre>
              )}
            </div>
          </Panel>
        </TabsContent>

        <TabsContent value="status">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {Object.entries(equipamentosPorLinha).map(([linha, eqs]) => (
              <section key={linha}>
                <h2 style={{ margin: '0 0 8px', fontSize: 15, fontWeight: 600, color: 'var(--isa-text)' }}>{linha}</h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 12 }}>
            {eqs.map(eq => (
              <Panel
                key={eq.codigo}
                title={
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'space-between' }}>
                    <span>{eq.nome} <span style={{ fontFamily: 'var(--isa-mono)', color: 'var(--isa-text-muted)', fontWeight: 400 }}>({eq.codigo})</span></span>
                    <Tag tone={eq.status === 'online' ? 'ok' : eq.status === 'offline' ? 'warn' : 'bad'}>{eq.status.toUpperCase()}</Tag>
                  </span>
                }
              >
                <div style={{ fontSize: 'var(--isa-fs-meta)', color: 'var(--isa-text)' }}>
                  <p style={{ margin: '2px 0' }}><b>Última Leitura:</b> {new Date(eq.ultima_leitura).toLocaleString('pt-BR')}</p>
                  <p style={{ margin: '2px 0' }}><b>Campos Presentes:</b> {eq.campos_presentes.length}</p>
                  <p style={{ margin: '2px 0' }}><b>Campos Faltando:</b> {eq.campos_faltando.length}</p>
                  {eq.erros.length > 0 && (
                    <div style={{ color: 'var(--isa-bad)', marginTop: 8 }}>
                      {eq.erros.map((e, i) => <div key={i}>{e}</div>)}
                    </div>
                  )}
                  <pre style={{
                    marginTop: 8, padding: 8,
                    background: 'var(--isa-bg-muted)',
                    fontSize: 11,
                    fontFamily: 'var(--isa-mono)',
                    borderRadius: 'var(--isa-radius)',
                    maxHeight: 140, overflowY: 'auto', whiteSpace: 'pre-wrap',
                  }}>{JSON.stringify(eq.dados_amostra, null, 2)}</pre>
                </div>
              </Panel>
            ))}
                </div>
              </section>
            ))}
            {equipamentos.length === 0 && (
              <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 32, color: 'var(--isa-text-muted)' }}>
                Nenhum equipamento encontrado.
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="logs">
          <Panel title="Logs do Sistema">
            <AlertList items={logsAsAlerts} emptyMsg="Nenhum erro registrado recentemente." />
          </Panel>
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Sub-átomo local: nó do diagrama de fluxo (CLP → coletor → influx → frontend).
const FluxoNode: React.FC<{ emoji: string; titulo: string; sub: string; status: 'ok' | 'bad' }> =
  ({ emoji, titulo, sub, status }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 90 }}>
    <div style={{
      width: 56, height: 56, borderRadius: '50%',
      display: 'grid', placeItems: 'center', marginBottom: 6,
      background: status === 'ok' ? 'var(--isa-ok-bg)' : 'var(--isa-bad-bg)',
      fontSize: 24,
    }}>{emoji}</div>
    <span style={{ fontSize: 'var(--isa-fs-default)', fontWeight: 600, color: 'var(--isa-text)' }}>{titulo}</span>
    <span style={{ fontSize: 'var(--isa-fs-meta)', color: 'var(--isa-text-muted)' }}>{sub}</span>
  </div>
);

const Conector: React.FC<{ label: string }> = ({ label }) => (
  <div style={{ position: 'relative', flex: '0 0 50px', minWidth: 50, height: 2, background: 'var(--isa-border)' }}>
    <div style={{ position: 'absolute', top: -16, left: '50%', transform: 'translateX(-50%)', fontSize: 10, color: 'var(--isa-text-muted)', whiteSpace: 'nowrap' }}>
      {label}
    </div>
  </div>
);

export default DiagnosticosLogs;
