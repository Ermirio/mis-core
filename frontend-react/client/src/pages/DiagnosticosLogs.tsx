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

const DiagnosticosLogs: React.FC = () => {
  const navigate = useNavigate();
  const [equipamentos, setEquipamentos] = useState<EquipamentoStatus[]>([]);
  const [diagnosticos, setDiagnosticos] = useState<DiagnosticoFluxo[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedEquipamento, setExpandedEquipamento] = useState<string | null>(null);
  const [filtroStatus, setFiltroStatus] = useState<'todos' | 'online' | 'offline' | 'erro'>('todos');

  // Campos esperados que devem vir do CLP
  const CAMPOS_ESPERADOS = [
    'contagem_entrada',
    'contagem_saida',
    'descarte',
    'percentual_descarte',
    'velocidade_atual',
    'estado_maquina',
    'temperatura',
    'pressao',
    'ordem_producao',
    'sku_codigo',
    'descricao',
    'formato_gramas',
    'oee',
    'disponibilidade',
    'performance',
    'qualidade'
  ];

  // Função para diagnosticar um equipamento
  const diagnosticarEquipamento = async (equipamento: any) => {
    try {
      // 1. Buscar dados em tempo real do Flask
      const flaskResponse = await fetch(
        `${FLASK_API_URL}/realtime/status/${equipamento.codigo}`,
        { signal: AbortSignal.timeout(5000) }
      ).catch(() => null);

      const dadosFlask = flaskResponse?.ok ? await flaskResponse.json() : null;

      // 2. Buscar configuração do Django
      const djangoResponse = await fetch(
        `${DJANGO_API_URL}/equipamentos/${equipamento.id}/`,
        { signal: AbortSignal.timeout(5000) }
      ).catch(() => null);

      const dadosDjango = djangoResponse?.ok ? await djangoResponse.json() : null;

      // Analisar campos presentes
      const medicoes = dadosFlask?.medicoes || {};
      const camposPresentesSet = new Set(Object.keys(medicoes));
      const camposFaltandoSet = new Set(CAMPOS_ESPERADOS.filter(c => !camposPresentesSet.has(c)));

      // Detectar erros
      const erros: string[] = [];
      
      if (!dadosFlask) {
        erros.push('❌ Flask não está respondendo - Verifique se está rodando em http://127.0.0.1:5000');
      }
      
      if (!dadosDjango) {
        erros.push('❌ Django não está respondendo - Verifique se está rodando em http://127.0.0.1:8000');
      }

      if (camposFaltandoSet.has('sku_codigo')) {
        erros.push('⚠️ SKU não está sendo coletado - Verifique configuração de tags no Django Admin');
      }

      if (camposFaltandoSet.has('descricao')) {
        erros.push('⚠️ Descrição do produto não está sendo coletada - Verifique configuração de tags');
      }

      if (camposFaltandoSet.has('oee') && camposFaltandoSet.has('disponibilidade')) {
        erros.push('⚠️ OEE não está sendo calculado - Verifique se métricas estão sendo consolidadas no Django');
      }

      if (camposFaltandoSet.has('ordem_producao')) {
        erros.push('⚠️ Ordem de Produção não está sendo coletada - Verifique NodeID no OPC');
      }

      if (camposFaltandoSet.has('formato_gramas')) {
        erros.push('⚠️ Formato não está sendo coletado - Verifique configuração de tags');
      }

      return {
        codigo: equipamento.codigo,
        nome: equipamento.nome,
        linha: equipamento.linha_nome || 'N/A',
        status: dadosFlask ? 'online' : (dadosDjango ? 'offline' : 'erro'),
        ultima_leitura: dadosFlask?.timestamp || 'N/A',
        campos_presentes: Array.from(camposPresentesSet),
        campos_faltando: Array.from(camposFaltandoSet),
        dados_amostra: medicoes,
        erros
      };
    } catch (error) {
      return {
        codigo: equipamento.codigo,
        nome: equipamento.nome,
        linha: equipamento.linha_nome || 'N/A',
        status: 'erro',
        ultima_leitura: 'N/A',
        campos_presentes: [],
        campos_faltando: CAMPOS_ESPERADOS,
        dados_amostra: {},
        erros: [`Erro ao diagnosticar: ${error}`]
      };
    }
  };

  // Carregar dados iniciais
  const carregarDados = async () => {
    try {
      setLoading(true);

      // Buscar lista de equipamentos
      const response = await fetch(`${DJANGO_API_URL}/equipamentos/`);
      const data = await response.json();

      // Diagnosticar cada equipamento
      const diagnosticos = await Promise.all(
        data.results.map((eq: any) => diagnosticarEquipamento(eq))
      );

      setEquipamentos(diagnosticos);

      // Gerar logs de diagnóstico
      const logs: DiagnosticoFluxo[] = [];
      diagnosticos.forEach(eq => {
        eq.erros.forEach(erro => {
          logs.push({
            timestamp: new Date().toISOString(),
            equipamento: eq.codigo,
            etapa: erro.includes('Flask') ? 'flask' : 
                   erro.includes('Django') ? 'django' :
                   erro.includes('OPC') ? 'coletor' : 'frontend',
            status: erro.includes('❌') ? 'erro' : 'aviso',
            mensagem: erro,
            detalhes: {}
          });
        });
      });

      setDiagnosticos(logs);
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh
  useEffect(() => {
    carregarDados();

    if (autoRefresh) {
      const interval = setInterval(carregarDados, 10000); // 10 segundos
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  // Filtrar equipamentos
  const equipamentosFiltrados = equipamentos.filter(eq => {
    if (filtroStatus === 'todos') return true;
    return eq.status === filtroStatus;
  });

  // Exportar logs
  const exportarLogs = () => {
    const conteudo = JSON.stringify({
      timestamp: new Date().toISOString(),
      equipamentos,
      diagnosticos
    }, null, 2);

    const blob = new Blob([conteudo], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `diagnosticos-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/')}
            className="text-gray-600"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Voltar
          </Button>
          <h1 className="text-3xl font-bold text-gray-900">Diagnósticos e Logs</h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={carregarDados}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={exportarLogs}
          >
            <Download className="w-4 h-4 mr-2" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Alerta de Auto-refresh */}
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

      {/* Tabs */}
      <Tabs defaultValue="status" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="status">Status dos Equipamentos</TabsTrigger>
          <TabsTrigger value="logs">Logs de Erro</TabsTrigger>
          <TabsTrigger value="fluxo">Fluxo de Dados</TabsTrigger>
        </TabsList>

        {/* Tab: Status */}
        <TabsContent value="status" className="space-y-4">
          {/* Filtros */}
          <div className="flex gap-2">
            {(['todos', 'online', 'offline', 'erro'] as const).map(status => (
              <Button
                key={status}
                variant={filtroStatus === status ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFiltroStatus(status)}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </Button>
            ))}
          </div>

          {/* Cards de Equipamentos */}
          <div className="grid gap-4">
            {equipamentosFiltrados.map(eq => (
              <Card key={eq.codigo} className="cursor-pointer hover:shadow-lg transition-shadow">
                <CardHeader
                  onClick={() => setExpandedEquipamento(
                    expandedEquipamento === eq.codigo ? null : eq.codigo
                  )}
                  className="pb-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {eq.status === 'online' && (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      )}
                      {eq.status === 'offline' && (
                        <AlertCircle className="w-5 h-5 text-yellow-500" />
                      )}
                      {eq.status === 'erro' && (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                      <div>
                        <h3 className="font-semibold text-gray-900">{eq.nome}</h3>
                        <p className="text-sm text-gray-500">{eq.codigo} • {eq.linha}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={eq.status === 'online' ? 'default' : 'secondary'}
                        className={
                          eq.status === 'online' ? 'bg-green-500' :
                          eq.status === 'offline' ? 'bg-yellow-500' :
                          'bg-red-500'
                        }
                      >
                        {eq.status.toUpperCase()}
                      </Badge>
                      {expandedEquipamento === eq.codigo ? (
                        <EyeOff className="w-4 h-4 text-gray-400" />
                      ) : (
                        <Eye className="w-4 h-4 text-gray-400" />
                      )}
                    </div>
                  </div>
                </CardHeader>

                {/* Conteúdo expandido */}
                {expandedEquipamento === eq.codigo && (
                  <CardContent className="space-y-4">
                    {/* Última leitura */}
                    <div className="text-sm text-gray-600">
                      <strong>Última leitura:</strong> {eq.ultima_leitura}
                    </div>

                    {/* Campos presentes */}
                    <div>
                      <h4 className="font-semibold text-sm text-gray-900 mb-2">
                        ✅ Campos Presentes ({eq.campos_presentes.length})
                      </h4>
                      <div className="flex flex-wrap gap-1">
                        {eq.campos_presentes.map(campo => (
                          <Badge key={campo} variant="outline" className="bg-green-50 text-green-700 border-green-200">
                            {campo}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    {/* Campos faltando */}
                    {eq.campos_faltando.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-sm text-gray-900 mb-2">
                          ❌ Campos Faltando ({eq.campos_faltando.length})
                        </h4>
                        <div className="flex flex-wrap gap-1">
                          {eq.campos_faltando.map(campo => (
                            <Badge key={campo} variant="outline" className="bg-red-50 text-red-700 border-red-200">
                              {campo}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Erros */}
                    {eq.erros.length > 0 && (
                      <Alert className="border-red-200 bg-red-50">
                        <AlertCircle className="h-4 w-4 text-red-600" />
                        <AlertDescription className="text-red-800">
                          <div className="space-y-1">
                            {eq.erros.map((erro, idx) => (
                              <div key={idx} className="text-sm">{erro}</div>
                            ))}
                          </div>
                        </AlertDescription>
                      </Alert>
                    )}

                    {/* Amostra de dados */}
                    {Object.keys(eq.dados_amostra).length > 0 && (
                      <div>
                        <h4 className="font-semibold text-sm text-gray-900 mb-2">Amostra de Dados</h4>
                        <div className="bg-gray-100 p-3 rounded text-xs font-mono overflow-auto max-h-48">
                          <pre>{JSON.stringify(eq.dados_amostra, null, 2)}</pre>
                        </div>
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tab: Logs */}
        <TabsContent value="logs" className="space-y-4">
          <div className="space-y-2">
            {diagnosticos.map((log, idx) => (
              <Card key={idx} className={
                log.status === 'erro' ? 'border-red-200 bg-red-50' :
                log.status === 'aviso' ? 'border-yellow-200 bg-yellow-50' :
                'border-green-200 bg-green-50'
              }>
                <CardContent className="pt-4">
                  <div className="flex items-start gap-3">
                    {log.status === 'erro' && <XCircle className="w-5 h-5 text-red-600 mt-0.5" />}
                    {log.status === 'aviso' && <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />}
                    {log.status === 'sucesso' && <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />}
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">
                          {log.equipamento}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {log.etapa}
                        </Badge>
                        <span className="text-xs text-gray-500">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm mt-1">{log.mensagem}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tab: Fluxo de Dados */}
        <TabsContent value="fluxo" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Fluxo de Dados Esperado</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                {[
                  { etapa: '1. CLP', descricao: 'Dados coletados do controlador lógico programável' },
                  { etapa: '2. OPC UA', descricao: 'Dados lidos via protocolo OPC UA' },
                  { etapa: '3. Coletor', descricao: 'Aplicação coletor.py mapeia tags e envia para Flask' },
                  { etapa: '4. Flask', descricao: 'API Flask recebe dados e armazena no InfluxDB' },
                  { etapa: '5. InfluxDB', descricao: 'Banco de dados de série temporal armazena dados' },
                  { etapa: '6. Django', descricao: 'API Django fornece configuração e cálculos consolidados' },
                  { etapa: '7. React', descricao: 'Frontend consome dados de Flask e Django e exibe' }
                ].map((item, idx) => (
                  <div key={idx} className="flex gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm font-semibold text-blue-600">
                      {idx + 1}
                    </div>
                    <div>
                      <p className="font-semibold text-sm">{item.etapa}</p>
                      <p className="text-sm text-gray-600">{item.descricao}</p>
                    </div>
                  </div>
                ))}
              </div>

              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Se algum equipamento está com status "Offline" ou "Erro", verifique o fluxo acima para identificar em qual etapa o problema ocorre.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          {/* Checklist de Verificação */}
          <Card>
            <CardHeader>
              <CardTitle>Checklist de Verificação</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {[
                { item: 'CLP está ligado e rodando', check: '✓' },
                { item: 'OPC Server está rodando', check: '✓' },
                { item: 'Coletor está rodando (coletor.py)', check: '✓' },
                { item: 'Flask está rodando (http://127.0.0.1:5000)', check: '✓' },
                { item: 'InfluxDB está rodando (http://127.0.0.1:8086)', check: '✓' },
                { item: 'Django está rodando (http://127.0.0.1:8000)', check: '✓' },
                { item: 'Tags estão configuradas no Django Admin', check: '✓' },
                { item: 'NodeIDs do OPC estão corretos', check: '✓' }
              ].map((item, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" id={`check-${idx}`} className="w-4 h-4" />
                  <label htmlFor={`check-${idx}`} className="text-gray-700">{item.item}</label>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DiagnosticosLogs;
