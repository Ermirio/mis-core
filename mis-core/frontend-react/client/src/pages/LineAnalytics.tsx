import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';
import { ProfileManager } from '@/components/Analytics/ProfileManager';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import MainLayout from '@/components/layout/MainLayout';
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import {
    CalendarIcon, Loader2, RefreshCw,
    BarChart2, TrendingUp, Activity, ScatterChart as ScatterIcon, Grid,
    Settings, Filter, Download, ChevronsRight, Info, Plus, Trash2, Edit,
    Box, Layers
} from "lucide-react";
import { format, subHours } from "date-fns";
import { ptBR } from "date-fns/locale";

import { DJANGO_API_URL as DJANGO_API, FLASK_API_URL as FLASK_API } from '@/config/api';
import { mockAnalyzeStats, mockAnalyzeTimeseries, mockAnalyzeCorrelation } from '@/mocks/demoData';
import { TimeRangePicker, defaultRange, type TimeRange, Note, StatsGrid } from '@/components/v2';
import { describe, fmt as numFmt } from '@/components/v2/stats';

const ESTADO_VALUE_MAPPING: Record<number, { label: string; color: string }> = {
    1:   { label: 'Produzindo',              color: '#16a34a' },
    2:   { label: 'Aguard. Anterior',        color: '#06b6d4' },
    3:   { label: 'Seguinte Bloqueado',      color: '#f97316' },
    4:   { label: 'Falha / Parado',          color: '#dc2626' },
    5:   { label: 'Setup / Troca SKU',       color: '#a855f7' },
    6:   { label: 'Teste de Projeto',        color: '#0ea5e9' },
    7:   { label: 'Aguard. Manutenção',      color: '#78716c' },
    8:   { label: 'Em Manutenção',           color: '#991b1b' },
    9:   { label: 'Falta de Material',       color: '#d97706' },
    11:  { label: 'Partindo',               color: '#84cc16' },
    12:  { label: 'Aguard. Condições',      color: '#64748b' },
    13:  { label: 'Parando',               color: '#f59e0b' },
    999: { label: 'Offline',               color: '#6b7280' },
};

interface Tag {
    id: number;
    nome: string; // Sensor name
    tag_influxdb: string; // Was node_id? No, Sensor has tag_influxdb
    equipamento_nome: string;
    equipamento_code: string;
    linha_nome: string; // Nome da linha para alias legível
    lsl?: number;
    usl?: number;
    nominal?: number;
    isStandard?: boolean;
    isDiscrete?: boolean;           // ← NOVO: flag para variável discreta/categórica
    valueMapping?: Record<number, { label: string; color: string }>;  // ← NOVO: mapeamento valor→legenda
}

interface Equipamento {
    id: number;
    nome: string;
    codigo: string;
    sensores: any[]; // Changed from tags_coleta
}

interface Linha {
    id: number;
    nome: string;
    codigo: string;
    equipamentos: Equipamento[];
}

const MOCK_LINHAS_ANALYTICS: Linha[] = [
  { id: 1, codigo: "ENV-01", nome: "Envase 01", equipamentos: [
    { id: 11, codigo: "ENV-01-ENCR", nome: "Enchedora",  sensores: [
      { id: 1001, nome: "Pressão Entrada (bar)",  tag_influxdb: "pressao_entrada",  lsl: 1.5, usl: 3.5, nominal: 2.5 },
      { id: 1002, nome: "Temperatura Produto (°C)", tag_influxdb: "temperatura_produto", lsl: 18, usl: 25, nominal: 20 },
      { id: 1003, nome: "Nível Tanque (%)",       tag_influxdb: "nivel_tanque",       lsl: 20, usl: 95, nominal: 60 },
    ]},
    { id: 12, codigo: "ENV-01-TAMP", nome: "Tampadora",  sensores: [
      { id: 1004, nome: "Torque Tampagem (Nm)",   tag_influxdb: "torque_tampagem",    lsl: 8, usl: 14, nominal: 11 },
    ]},
    { id: 13, codigo: "ENV-01-ROT",  nome: "Rotuladora", sensores: [
      { id: 1005, nome: "Tensão Filme (N)",        tag_influxdb: "tensao_filme",       lsl: 3, usl: 12, nominal: 7 },
    ]},
  ]},
  { id: 4, codigo: "EMP-01", nome: "Empacotamento 01", equipamentos: [
    { id: 41, codigo: "EMP-01-FORM", nome: "Formadora",  sensores: [
      { id: 2001, nome: "Pressão Corte (bar)",    tag_influxdb: "pressao_corte",      lsl: 4, usl: 8, nominal: 6 },
      { id: 2002, nome: "Temp. Selagem (°C)",     tag_influxdb: "temperatura_selagem",lsl: 140, usl: 180, nominal: 160 },
    ]},
    { id: 42, codigo: "EMP-01-CXDR", nome: "Caixaria",   sensores: [
      { id: 2003, nome: "Consumo Cola (g/min)",   tag_influxdb: "consumo_cola",        lsl: 0, usl: 50, nominal: 25 },
    ]},
  ]},
  { id: 7, codigo: "PAL-01", nome: "Paletização 01", equipamentos: [
    { id: 71, codigo: "PAL-01-ROBO", nome: "Robô Palletizador", sensores: [
      { id: 3001, nome: "Ciclos por Hora",         tag_influxdb: "ciclos_hora",        lsl: 40, usl: 80, nominal: 60 },
      { id: 3002, nome: "Corrente Motor (A)",      tag_influxdb: "corrente_motor",     lsl: 0, usl: 15, nominal: 8 },
    ]},
  ]},
];

interface TrendChart {
    id: number;
    name: string; // Added name
    selectedAliases: string[];
}

// ... (imports remain)
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";

// --- Componente isolado para a Matriz de Correlação ---
// Resolve problema de contexto JSX em closures/IIFEs dentro de componentes grandes
interface CorrMatrixProps {
    matrix: {
        columns: string[];
        values: number[][];
        p_values: number[][];
        method: string;
        n_points: number;
        resample_rule: string;
    };
    corrMinFilter: number;
    pvalToStars: (p: number) => string;
    timeseriesData: any;
    setScatterX: (v: string) => void;
    setScatterY: (v: string) => void;
    setActiveTab: (v: string) => void;
    handleRunAnalysis: (mode: 'stats' | 'correlation' | 'timeseries') => Promise<void>;
}

const CorrMatrixPlot = ({
    matrix, corrMinFilter, pvalToStars, timeseriesData,
    setScatterX, setScatterY, setActiveTab, handleRunAnalysis
}: CorrMatrixProps): React.ReactElement => {
    const { columns, values, p_values, method } = matrix;

    const textMatrix = values.map((row: number[], i: number) =>
        row.map((v: number, j: number) => {
            if (i === j) return '1.00';
            if (Math.abs(v) < corrMinFilter) return '';
            const stars = p_values ? pvalToStars(p_values[i][j]) : '';
            return `${(v * 100).toFixed(1)}%${stars}`;
        })
    );


    const hoverMatrix = values.map((row: number[], i: number) =>
        row.map((v: number, j: number) => {
            const p = p_values?.[i]?.[j];
            const pStr = (p !== undefined && i !== j)
                ? `<br>p-value: ${p < 0.0001 ? '<0.0001' : p.toFixed(4)}${pvalToStars(p) ? ` ${pvalToStars(p)}` : ' (ns)'}`
                : '';
            return `<b>${columns[j]}</b> x <b>${columns[i]}</b><br>r = ${v.toFixed(4)}${pStr}`;
        })
    );

    const handleClick = (data: any) => {
        const pt = data?.points?.[0];
        if (!pt) return;
        const xVar = pt.x as string;
        const yVar = pt.y as string;
        if (xVar === yVar) return;
        setScatterX(xVar);
        setScatterY(yVar);
        if (timeseriesData?.[xVar] && timeseriesData?.[yVar]) {
            setActiveTab('scatter');
        } else {
            handleRunAnalysis('timeseries').then(() => setActiveTab('scatter'));
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>
                    Matriz de Correlação — {method === 'spearman' ? 'Spearman' : 'Pearson'}
                </CardTitle>
                <CardDescription className="text-xs">
                    Clique numa célula para abrir o gráfico de dispersão do par. Células em branco estão abaixo do filtro mínimo.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Plot
                    data={[{
                        z: values,
                        x: columns,
                        y: columns,
                        type: 'heatmap',
                        colorscale: 'RdBu',
                        zmin: -1, zmax: 1,
                        text: textMatrix,
                        texttemplate: '%{text}',
                        textfont: { size: 11, color: 'black' },
                        hovertemplate: '%{customdata}<extra></extra>',
                        customdata: hoverMatrix,
                        xgap: 3,
                        ygap: 3,
                    } as any]}
                    layout={{
                        height: 600,
                        autosize: true,
                        title: { text: '' },
                        margin: { l: 160, r: 20, t: 20, b: 160 },
                        xaxis: { tickangle: -40 },
                        yaxis: { tickangle: 0 }
                    }}
                    useResizeHandler={true}
                    className="w-full"
                    onClick={handleClick}
                />
            </CardContent>
        </Card>
    );
};

// --- Componente isolado para Scatter com Trend Line ---
interface ScatterPlotProps {
    xKey: string;
    yKey: string;
    timeseriesData: any;
    calcLinearRegression: (x: number[], y: number[]) => { slope: number; intercept: number; xMin: number; xMax: number } | null;
}

const ScatterPlot = ({ xKey, yKey, timeseriesData, calcLinearRegression }: ScatterPlotProps): React.ReactElement => {
    const xVals: number[] = timeseriesData[xKey]?.values ?? [];
    const yVals: number[] = timeseriesData[yKey]?.values ?? [];
    const reg = calcLinearRegression(xVals, yVals);
    const n = xVals.length;
    const xMean = n ? xVals.reduce((a, b) => a + b, 0) / n : 0;
    const yMean = n ? yVals.reduce((a, b) => a + b, 0) / n : 0;
    const num = xVals.reduce((acc, xi, i) => acc + (xi - xMean) * (yVals[i] - yMean), 0);
    const den = Math.sqrt(
        xVals.reduce((acc, xi) => acc + (xi - xMean) ** 2, 0) *
        yVals.reduce((acc, yi) => acc + (yi - yMean) ** 2, 0)
    );
    const r = den === 0 ? 0 : num / den;
    const rLabel = r >= 0.7 ? 'Forte positiva' : r <= -0.7 ? 'Forte negativa' : Math.abs(r) >= 0.3 ? 'Moderada' : 'Fraca';
    const trendTraces: any[] = reg ? [{
        x: [reg.xMin, reg.xMax],
        y: [reg.slope * reg.xMin + reg.intercept, reg.slope * reg.xMax + reg.intercept],
        mode: 'lines',
        type: 'scatter',
        name: `Tendência (r=${r.toFixed(3)})`,
        line: { color: 'red', width: 2, dash: 'dash' }
    }] : [];
    return (
        <div>
            <div className="flex flex-wrap gap-3 mb-3 text-sm">
                <span className="bg-slate-100 px-3 py-1 rounded font-mono">r = {r.toFixed(4)}</span>
                <span className="bg-slate-100 px-3 py-1 rounded">{rLabel}</span>
                {reg && (
                    <span className="bg-slate-100 px-3 py-1 rounded font-mono text-xs">
                        y = {reg.slope.toFixed(4)}x + {reg.intercept.toFixed(4)}
                    </span>
                )}
                <span className="text-gray-400 text-xs self-center">n = {n} pontos</span>
            </div>
            <Plot
                data={[
                    {
                        x: xVals, y: yVals,
                        mode: 'markers', type: 'scatter', name: 'Dados',
                        marker: { color: 'rgba(59,130,246,0.5)', size: 7, line: { color: 'rgba(59,130,246,0.8)', width: 1 } }
                    },
                    ...trendTraces
                ]}
                layout={{
                    autosize: true, height: 480,
                    xaxis: { title: { text: xKey } },
                    yaxis: { title: { text: yKey } },
                    legend: { orientation: 'h', y: -0.15 },
                    margin: { l: 50, r: 20, t: 20, b: 60 }
                }}
                useResizeHandler={true}
                className="w-full"
            />
        </div>
    );
};

/**
 * computeInsights — sintetiza "descobertas" para storytelling com dados.
 *
 * Filosofia (data storytelling): a tabela de stats é boa para o cientista
 * de dados, mas o operador/engenheiro precisa de UMA FRASE que explica O
 * QUE ESTÁ ACONTECENDO. Esta função pega timeseriesData + selectedTags e
 * devolve cards do tipo "Variável X tem CV alto (12%) — instável".
 *
 * Heurísticas:
 *   - CV (coeficiente de variação) > 10% → "instável" (warn)
 *   - 1+ ponto > 3σ → "anomalia detectada" (bad)
 *   - LSL/USL definidos e Cpk < 1.33 → "fora de capabilidade" (bad)
 *   - drift detectado por Kendall τ > 0.5 → "tendência" (warn)
 */
interface Insight { tone: 'ok' | 'warn' | 'bad'; title: string; desc: string; }

function computeInsights(timeseriesData: any, selectedTags: any[]): Insight[] {
  if (!timeseriesData) return [];
  const out: Insight[] = [];
  for (const [alias, d] of Object.entries(timeseriesData) as [string, any][]) {
    const tag = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias);
    if (tag?.isDiscrete) continue;
    const ys = (d?.values || []).filter((v: any) => typeof v === 'number' && !isNaN(v));
    if (ys.length < 5) continue;
    const mean = ys.reduce((a: number, b: number) => a + b, 0) / ys.length;
    const std = Math.sqrt(ys.reduce((a: number, b: number) => a + (b - mean) ** 2, 0) / ys.length);
    const cv = mean !== 0 ? Math.abs(std / mean) * 100 : 0;
    const short = alias.split(' - ').pop() || alias;

    // Anomalia: pontos > 3σ
    const anomalies = ys.filter((v: number) => v > mean + 3 * std || v < mean - 3 * std).length;
    if (anomalies > 0) {
      out.push({
        tone: 'bad',
        title: `${anomalies} anomalia${anomalies > 1 ? 's' : ''} em ${short}`,
        desc: `Ponto${anomalies > 1 ? 's' : ''} fora de ±3σ — investigar evento de processo.`,
      });
    }

    // Capabilidade Cpk
    if (tag?.lsl != null && tag?.usl != null && std > 0) {
      const cpk = Math.min((tag.usl - mean) / (3 * std), (mean - tag.lsl) / (3 * std));
      if (cpk < 1.0) {
        out.push({ tone: 'bad', title: `${short} fora de controle`, desc: `Cpk=${cpk.toFixed(2)} — produção pode estar fora dos limites de especificação.` });
      } else if (cpk < 1.33) {
        out.push({ tone: 'warn', title: `${short} marginal`, desc: `Cpk=${cpk.toFixed(2)} — abaixo do alvo industrial 1.33.` });
      }
    }

    // CV > 10% — "instável"
    if (cv > 10 && ys.length > 10) {
      out.push({ tone: 'warn', title: `${short} instável`, desc: `CV=${cv.toFixed(1)}% — variabilidade alta vs. média.` });
    }

    // Drift por Kendall τ simples (proporção de pares concordantes)
    if (ys.length > 30) {
      let concord = 0, discord = 0;
      const sample = ys.length > 200 ? ys.filter((_: number, i: number) => i % Math.floor(ys.length / 200) === 0) : ys;
      for (let i = 0; i < sample.length - 1; i++) {
        for (let j = i + 1; j < sample.length; j++) {
          if (sample[j] > sample[i]) concord++;
          else if (sample[j] < sample[i]) discord++;
        }
      }
      const total = concord + discord;
      const tau = total > 0 ? (concord - discord) / total : 0;
      if (Math.abs(tau) > 0.5) {
        out.push({
          tone: 'warn',
          title: `Drift em ${short}`,
          desc: `Tendência ${tau > 0 ? 'crescente' : 'decrescente'} consistente (τ=${tau.toFixed(2)}).`,
        });
      }
    }
  }
  return out;
}


/**
 * detectWERules — Western Electric Rules para Controle Estatístico de Processo.
 *
 * Implementa as 4 regras clássicas (de 8) que mais agregam valor ao operador
 * de chão de fábrica. Detecção visual via marcadores no gráfico SPC.
 *
 *   Rule 1: 1 ponto fora de ±3σ                                  (alarme imediato)
 *   Rule 2: 9 pontos consecutivos do MESMO LADO da média          (drift / shift)
 *   Rule 3: 6 pontos consecutivos crescendo OU decrescendo        (trend)
 *   Rule 4: 14 pontos alternando ascendente-descendente           (over-control)
 *
 * Retorna lista de violações por índice (i, regra, descrição) — para o gráfico
 * destacar os pontos e a UI listar embaixo o que aconteceu.
 */
interface WEViolation { index: number; rule: 1 | 2 | 3 | 4; desc: string; }

function detectWERules(values: number[], mean: number, std: number): WEViolation[] {
  const violations: WEViolation[] = [];
  if (values.length < 9 || std === 0) return violations;
  const ucl = mean + 3 * std, lcl = mean - 3 * std;

  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (typeof v !== "number" || isNaN(v)) continue;

    // Rule 1 — fora de ±3σ
    if (v > ucl || v < lcl) {
      violations.push({ index: i, rule: 1, desc: `Ponto > 3σ (valor=${v.toFixed(2)}, limite=${(v > ucl ? ucl : lcl).toFixed(2)})` });
    }

    // Rule 2 — 9 pontos consecutivos do mesmo lado da média
    if (i >= 8) {
      const slice = values.slice(i - 8, i + 1);
      if (slice.every(x => typeof x === "number" && x > mean)) {
        violations.push({ index: i, rule: 2, desc: "9 pontos consecutivos acima da média" });
      } else if (slice.every(x => typeof x === "number" && x < mean)) {
        violations.push({ index: i, rule: 2, desc: "9 pontos consecutivos abaixo da média" });
      }
    }

    // Rule 3 — 6 pontos consecutivos sempre crescendo ou decrescendo
    if (i >= 5) {
      const slice = values.slice(i - 5, i + 1) as number[];
      let inc = true, dec = true;
      for (let k = 1; k < slice.length; k++) {
        if (slice[k] <= slice[k - 1]) inc = false;
        if (slice[k] >= slice[k - 1]) dec = false;
      }
      if (inc) violations.push({ index: i, rule: 3, desc: "6 pontos consecutivos crescendo (drift positivo)" });
      else if (dec) violations.push({ index: i, rule: 3, desc: "6 pontos consecutivos decrescendo (drift negativo)" });
    }

    // Rule 4 — 14 pontos alternando direção
    if (i >= 13) {
      const slice = values.slice(i - 13, i + 1) as number[];
      let alt = true;
      for (let k = 2; k < slice.length; k++) {
        const a = slice[k - 2], b = slice[k - 1], c = slice[k];
        const sig1 = b > a, sig2 = c > b;
        if (sig1 === sig2) { alt = false; break; }
      }
      if (alt) violations.push({ index: i, rule: 4, desc: "14 pontos alternando — possível over-controle" });
    }
  }
  return violations;
}


const LineAnalytics: React.FC = () => {
    const [linhas, setLinhas] = useState<Linha[]>([]);
    // Removed selectedLinhaId
    const [selectedTags, setSelectedTags] = useState<Tag[]>([]);

    // Time Range — agora datetime range estilo Grafana (POC)
    // PROBLEMA QUE RESOLVE (do diagnóstico):
    //   "Os filtros de tempos de analytics precisam ser baseados em data hora
    //    e não somente tempos fixos, bem semelhante ao como o grafana trabalha."
    const [tr, setTr] = useState<TimeRange>(() => defaultRange());
    // OFF-mask: equipamento desligado vira null (gap no gráfico) e sai das stats.
    // Delta: contadores acumulados são convertidos em delta por janela.
    // Os dois switches ficam no toolbar e entram no payload do backend.
    const [ignoreOff, setIgnoreOff] = useState(true);
    const [applyDelta, setApplyDelta] = useState(true);
    // Compat: ainda exportado pelo perfil antigo (loadProfile).
    const [hoursBack, setHoursBack] = useState<string>('24');

    // Data
    const [statsData, setStatsData] = useState<any[]>([]);
    const [correlationData, setCorrelationData] = useState<any>(null);
    const [timeseriesData, setTimeseriesData] = useState<any>(null);
    const [trendCharts, setTrendCharts] = useState<TrendChart[]>([]);
    const [scatterX, setScatterX] = useState<string>('');
    const [scatterY, setScatterY] = useState<string>('');
    const [activeTab, setActiveTab] = useState<string>('stats');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [corrMethod, setCorrMethod] = useState<'pearson' | 'spearman'>('pearson');
    const [corrMinFilter, setCorrMinFilter] = useState<number>(0);

    // ── Trend/SPC enhancements ────────────────────────────────────────
    // Live mode: re-roda analysis a cada 10s, com tr.to deslizando para now.
    // Útil para "ver os dados em tempo real" como o usuário pediu.
    const [liveMode, setLiveMode] = useState(false);
    // Anomaly markers: destaca pontos > 3σ no Trend (regra clássica Shewhart).
    const [showAnomalies, setShowAnomalies] = useState(true);
    // Trendline: regressão linear sobreposta. Ajuda a ver drift.
    const [showTrendline, setShowTrendline] = useState(false);

    // Fetch Structure
    useEffect(() => {
        axios.get(`${DJANGO_API}/linhas/`)
            .then(res => {
                const list = res.data.results || res.data || [];
                setLinhas(list.length > 0 ? list : MOCK_LINHAS_ANALYTICS);
            })
            .catch(() => setLinhas(MOCK_LINHAS_ANALYTICS));
    }, []);

    // ── Live mode: refetch automático a cada 10s ──
    // Importante: usa runAllAnalyses (paralelo) e atualiza o `tr.to = now`
    // para que a janela "deslize" como Grafana em modo "Last 30m".
    useEffect(() => {
        if (!liveMode || selectedTags.length === 0) return;
        const id = setInterval(() => {
            const span = tr.to.getTime() - tr.from.getTime();
            const newTo = new Date();
            const newFrom = new Date(newTo.getTime() - span);
            setTr(prev => ({ ...prev, from: newFrom, to: newTo }));
            runAllAnalyses();
        }, 10_000);
        return () => clearInterval(id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [liveMode, selectedTags.length]);

    /**
     * runAllAnalyses — dispara as 3 análises em paralelo.
     *
     * Por que existe: a UX antiga tinha 3 botões (Stats, Gerar Gráficos,
     * Correlação) que pareciam fazer coisas diferentes mas, do ponto de vista
     * do usuário (cientista de dados em chão de fábrica), são UMA SÓ
     * "explorar este conjunto de variáveis nesta janela". Em vez de obrigar o
     * usuário a clicar 3 vezes, fazemos a chamada paralela e o switch de aba
     * apenas troca a visualização do dado já cacheado.
     */
    const runAllAnalyses = async () => {
        if (selectedTags.length === 0) {
            setError("Selecione pelo menos uma variável.");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            // Promise.allSettled para não falhar tudo se um endpoint estiver fora.
            // Cada handleRunAnalysis já tem fallback para mock interno.
            await Promise.allSettled([
                handleRunAnalysis('stats',       /* silent */ true),
                handleRunAnalysis('timeseries',  /* silent */ true),
                handleRunAnalysis('correlation', /* silent */ true),
            ]);
        } catch (err) {
            console.error('runAllAnalyses falhou:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleRunAnalysis = async (
        mode: 'stats' | 'correlation' | 'timeseries',
        silent: boolean = false,
    ) => {
        // ... (logic remains same, just verify it uses selectedTags which is global now)
        if (selectedTags.length === 0) {
            if (!silent) setError("Selecione pelo menos uma variável.");
            return;
        }

        if (!silent) {
            setLoading(true);
            setError(null);
        }

        try {
            // Range datetime estilo Grafana — tr.from/tr.to são canônicos.
            // O backend (Flask /analyze + FastAPI /api/v2/analyze) deve respeitar
            // start_time/end_time em ISO 8601 UTC; ignore_off e apply_delta são
            // novos flags para EDA correto (vide diagnóstico do projeto).
            const payload: any = {
                variables: selectedTags.map(t => ({
                    tag_influx: t.tag_influxdb,
                    equipamento_code: t.equipamento_code,
                    alias: `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}`,
                    lsl: t.lsl,
                    usl: t.usl,
                    nominal: t.nominal
                })),
                start_time: tr.from.toISOString(),
                end_time:   tr.to.toISOString(),
                granularity: tr.granularity,        // 'auto' | '1m' | '5m' | '15m' | '1h' | '1d'
                ignore_off: ignoreOff,              // mascara equipamento OFF como null
                apply_delta: applyDelta,            // converte contador acumulado em delta por janela
            };
            if (mode === 'correlation') {
                payload.method = corrMethod;
            }

            let endpoint = '';
            if (mode === 'stats') endpoint = '/analyze/stats';
            else if (mode === 'correlation') endpoint = '/analyze/correlation';
            else endpoint = '/analyze/timeseries';

            const mockVars = payload.variables;
            let responseData: any = null;

            try {
                const res = await axios.post(`${FLASK_API}${endpoint}`, payload);
                const isEmpty = !res.data ||
                    (Array.isArray(res.data) && (res.data.length === 0 || res.data.every((r: any) => r.error === 'No data found' || r.error === 'Empty data'))) ||
                    (typeof res.data === 'object' && Object.keys(res.data).length === 0);
                responseData = isEmpty ? null : res.data;
            } catch {
                // API unavailable → fall through to mock
            }

            // Fallback to mock when no real data
            if (!responseData) {
                if (mode === 'stats')        responseData = mockAnalyzeStats(mockVars);
                else if (mode === 'correlation') responseData = mockAnalyzeCorrelation(mockVars);
                else                         responseData = mockAnalyzeTimeseries(mockVars);
            }

            if (mode === 'stats') {
                setStatsData(responseData);
                if (!silent) setActiveTab('stats');
            } else if (mode === 'correlation') {
                if (responseData?.error) {
                    if (!silent) {
                        setError(`Correlação: ${responseData.error}`);
                        setLoading(false);
                    }
                    return;
                }
                setCorrelationData(responseData);
                if (!silent) setActiveTab('correlation');
            } else {
                setTimeseriesData(responseData);
                setTrendCharts([{
                    id: Date.now(),
                    name: 'Painel Geral',
                    selectedAliases: Object.keys(responseData)
                }]);
                if (!silent) setActiveTab('trend');
            }

        } catch (err: any) {
            console.error("Erro na análise:", err);
            if (!silent) setError("Erro inesperado ao executar análise.");
        } finally {
            if (!silent) setLoading(false);
        }
    };

    // Helper to process trees (memoized ideally, but safe here)
    // Flatten tags logic moved inside render or helper
    // No more getAvailableTags depending on single line.

    const toggleTag = (tag: any) => {
        if (selectedTags.find(t => t.id === tag.id)) {
            setSelectedTags(selectedTags.filter(t => t.id !== tag.id));
        } else {
            setSelectedTags([...selectedTags, tag]);
        }
    };

    // Tag generation helper - Métricas consolidadas da LINHA
    const getLineConsolidatedTags = (linha: Linha) => {
        const consolidatedMetrics = [
            { nome: 'Produção Total (tons)', tag: 'producao_linha_tons', desc: 'Produção acumulada da linha' },
            { nome: 'Descarte Total (tons)', tag: 'descarte_linha_tons', desc: 'Descarte acumulado da linha' },
            { nome: 'Descarte (%)', tag: 'descarte_linha_perc', desc: 'Percentual de descarte' },
            { nome: 'OEE Linha', tag: 'oee_linha', desc: 'OEE agregado da linha' },
            { nome: 'Disponibilidade', tag: 'disponibilidade_linha', desc: 'Disponibilidade da linha' },
            { nome: 'Performance', tag: 'performance_linha', desc: 'Performance da linha' },
            { nome: 'Qualidade', tag: 'qualidade_linha', desc: 'Qualidade da linha' },
            { nome: 'Vazão Real (ton/h)', tag: 'vazao_linha_ton_h', desc: 'Taxa de produção' },
            { nome: 'Give Away (kg)', tag: 'giveaway_linha_kg', desc: 'Excesso de peso (kg)' },
            { nome: 'Give Away (%)', tag: 'giveaway_linha_perc', desc: 'Percentual de perda por peso' }
        ];

        return consolidatedMetrics.map(m => ({
            id: `linha-${linha.codigo}-${m.tag}`,
            nome: m.nome,
            tag_influxdb: m.tag,
            equipamento_nome: '📊 Consolidado',
            equipamento_code: linha.codigo,  // Usa código da linha para query especial
            linha_nome: linha.nome,
            isConsolidated: true,
            isStandard: false
        }));
    };

    // Tag generation helper - Métricas por EQUIPAMENTO
    const getEquipmentTags = (linha: Linha, eq: Equipamento) => {
        let tags: any[] = [];
        // Standard Metrics
        const standardMetrics = [
            { nome: 'Velocidade', tag: 'velocidade_atual' },
            { nome: 'OEE', tag: 'oee' },
            { nome: 'Produção', tag: 'contagem_saida' },
            { nome: 'Descarte', tag: 'descarte' },
            { nome: 'Estado', tag: 'estado', isDiscrete: true, valueMapping: ESTADO_VALUE_MAPPING }
        ];

        standardMetrics.forEach(m => {
            tags.push({
                id: `std-${eq.codigo}-${m.tag}`,
                nome: m.nome,
                tag_influxdb: m.tag,
                equipamento_nome: eq.nome,
                equipamento_code: eq.codigo,
                linha_nome: linha.nome,
                isStandard: true,
                isDiscrete: (m as any).isDiscrete ?? false,
                valueMapping: (m as any).valueMapping ?? undefined,
            });
        });

        // Dynamic Sensors
        if (eq.sensores) {
            eq.sensores.forEach((s: any) => {
                tags.push({
                    id: s.id,
                    nome: s.nome,
                    tag_influxdb: s.tag_influxdb,
                    equipamento_nome: eq.nome,
                    equipamento_code: eq.codigo,
                    linha_nome: linha.nome,
                    lsl: s.lsl,
                    usl: s.usl,
                    nominal: s.nominal,
                    isStandard: false
                });
            });
        }
        return tags;
    };

    // Filter Logic
    const filterMatch = (text: string) => {
        if (!searchTerm) return true;
        return text.toLowerCase().includes(searchTerm.toLowerCase());
    };

    // [Trend/SPC fix] Defensa contra arrays fora de ordem cronológica.
    // O backend já faz sort_index, mas se houver regressão (ou se o frontend
    // estiver consumindo cache antigo), o gráfico de linha do Plotly desenha
    // na ORDEM DOS ARRAYS — não reordena por X mesmo com type:'date'. Quando
    // a ordem se perde, a linha vira zigueza-zague e visualmente "parece
    // ordenada por valor". Aqui re-ordenamos sempre antes do plot.
    const sortByTimestamp = (
        timestamps: string[] | undefined,
        values: any[] | undefined,
    ): { x: string[]; y: any[] } => {
        const ts = timestamps || [];
        const vs = values || [];
        if (ts.length !== vs.length || ts.length < 2) {
            return { x: ts, y: vs };
        }
        // Pareia, ordena por timestamp ISO (string-sortable: ISO 8601 é lexicograficamente
        // crescente igual a temporal), e desempareia.
        const pairs = ts.map((t, i) => [t, vs[i]] as [string, any]);
        pairs.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
        return {
            x: pairs.map(p => p[0]),
            y: pairs.map(p => p[1]),
        };
    };

    // Regressão linear simples para trend line no scatter
    const calcLinearRegression = (xArr: number[], yArr: number[]) => {
        const n = xArr.length;
        if (n < 2) return null;
        const xMean = xArr.reduce((a, b) => a + b, 0) / n;
        const yMean = yArr.reduce((a, b) => a + b, 0) / n;
        const ssXY = xArr.reduce((acc, xi, i) => acc + (xi - xMean) * (yArr[i] - yMean), 0);
        const ssXX = xArr.reduce((acc, xi) => acc + (xi - xMean) ** 2, 0);
        if (ssXX === 0) return null;
        const slope = ssXY / ssXX;
        const intercept = yMean - slope * xMean;
        const xMin = Math.min(...xArr);
        const xMax = Math.max(...xArr);
        return { slope, intercept, xMin, xMax };
    };

    // P-value → marcador de significância
    const pvalToStars = (p: number) => {
        if (p < 0.001) return '***';
        if (p < 0.01) return '**';
        if (p < 0.05) return '*';
        return '';
    };

    // Export CSV da matriz de correlação
    const downloadCorrelationCSV = () => {
        if (!correlationData?.correlation_matrix) return;
        const { columns, values, p_values } = correlationData.correlation_matrix;
        let csv = 'Variável,' + columns.join(',') + '\n';
        values.forEach((row: number[], i: number) => {
            const cells = row.map((v: number, j: number) => {
                const p = p_values?.[i]?.[j];
                const stars = p !== undefined ? pvalToStars(p) : '';
                return `${v.toFixed(4)}${stars}`;
            });
            csv += `${columns[i]},${cells.join(',')}\n`;
        });
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `correlacao_${corrMethod}_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const downloadCSV = () => {
        if (!timeseriesData) return;
        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Time,Variable,Value\n";

        // Export simplified CSV (first variable timestamps logic or union)
        // For simplicity, iterating all data
        Object.entries(timeseriesData).forEach(([alias, data]: [string, any]) => {
            data.timestamps.forEach((t: string, i: number) => {
                csvContent += `${t},${alias},${data.values[i]}\n`;
            });
        });

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "analise_dados.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // Multi-Chart Handlers
    const addChart = () => {
        setTrendCharts([...trendCharts, {
            id: Date.now(),
            name: `Painel ${trendCharts.length + 1}`,
            selectedAliases: []
        }]);
    };

    const removeChart = (id: number) => {
        setTrendCharts(trendCharts.filter(c => c.id !== id));
    };

    const updateChartName = (id: number, newName: string) => {
        setTrendCharts(trendCharts.map(c => c.id === id ? { ...c, name: newName } : c));
    };

    const toggleChartVariable = (chartId: number, alias: string) => {
        setTrendCharts(trendCharts.map(c => {
            if (c.id === chartId) {
                const isSelected = c.selectedAliases.includes(alias);
                return {
                    ...c,
                    selectedAliases: isSelected
                        ? c.selectedAliases.filter(a => a !== alias)
                        : [...c.selectedAliases, alias]
                };
            }
            return c;
        }));
    };

    // Carregar perfil salvo
    const loadProfile = (config: any) => {
        setSelectedTags(
            (config.selectedTags || []).map((t: any) => {
                if (t.tag_influxdb === 'estado' && !t.isDiscrete) {
                    return { ...t, isDiscrete: true, valueMapping: ESTADO_VALUE_MAPPING };
                }
                return t;
            })
        );
        setHoursBack(config.hoursBack || '8');
        setActiveTab(config.activeTab || 'stats');
        setTrendCharts(config.trendCharts || []);
        setScatterX(config.scatterX || '');
        setScatterY(config.scatterY || '');
    };

    return (
        <div className="an__page">
            <header className="an__header">
                <div>
                    <h1 className="an__title">Análise de Variáveis</h1>
                    <p className="an__subtitle">Selecione variáveis, escolha o período e gere os gráficos</p>
                </div>
                <div className="an__actions">
                    {linhas.length > 0 && (
                        <ProfileManager
                            linhaId={linhas[0]?.id}
                            currentState={{ selectedTags, hoursBack, activeTab, trendCharts, scatterX, scatterY }}
                            onLoadProfile={loadProfile}
                        />
                    )}
                    {/* CTA único — substitui os 3 botões antigos.
                        runAllAnalyses dispara stats + timeseries + correlation
                        em paralelo. Trocar de aba não refaz fetch (zero-cost). */}
                    <button
                        type="button"
                        className="an__btn an__btn--primary"
                        onClick={runAllAnalyses}
                        disabled={loading || selectedTags.length === 0}
                        title={selectedTags.length === 0 ? "Selecione ao menos uma variável" : "Executa stats + tendência + correlação"}
                    >
                        {loading ? "Analisando…" : `Analisar (${selectedTags.length})`}
                    </button>
                    {(timeseriesData || statsData.length > 0) && (
                        <button type="button" className="an__btn an__btn--ghost" onClick={downloadCSV}>Exportar CSV</button>
                    )}
                </div>
            </header>

            {error && <div className="an__error">{error}</div>}

            <div className="an__body">
                {/* ── Painel de variáveis ── */}
                <Card className="an__panel">
                    <CardHeader className="pb-2">
                        <CardTitle className="an__panel-title">
                            <Settings className="h-4 w-4" />
                            Variáveis
                            <span className="an__badge">{selectedTags.length} sel.</span>
                        </CardTitle>
                        <CardDescription className="an__panel-desc">
                            {/* Período agora controlado pelo TimeRangePicker no toolbar acima.
                                Mantemos um indicador rápido aqui pra contexto visual. */}
                            <span style={{ fontFamily: 'var(--isa-mono)', color: 'var(--isa-text-muted)' }}>
                                {Math.round((tr.to.getTime() - tr.from.getTime()) / 3600000)}h ·
                                granularidade {tr.granularity}
                            </span>
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col gap-3 overflow-hidden pt-2">
                        <div className="an__search-wrap">
                            <Filter className="an__search-icon" />
                            <Input
                                placeholder="Buscar variável…"
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                                className="an__search-input"
                            />
                        </div>

                        <ScrollArea className="flex-1 w-full h-full an__scroll">
                            <Accordion type="multiple" className="w-full pr-3">
                                {linhas.map(linha => {
                                    return (
                                        <AccordionItem key={linha.id} value={`line-${linha.id}`} className="border-b last:border-0">
                                            <AccordionTrigger className="hover:no-underline py-2 sticky top-0 bg-slate-50 dark:bg-slate-900/50 z-10">
                                                <span className="font-semibold text-sm text-left">{linha.nome} ({linha.codigo})</span>
                                            </AccordionTrigger>
                                            <AccordionContent className="pb-2">
                                                <div className="pl-1 flex flex-col gap-1">
                                                    {/* === CONSOLIDADO DA LINHA === */}
                                                    {(() => {
                                                        const consolidatedTags = getLineConsolidatedTags(linha);
                                                        const visibleConsolidated = searchTerm
                                                            ? consolidatedTags.filter(t => filterMatch(t.nome) || filterMatch('consolidado'))
                                                            : consolidatedTags;

                                                        if (visibleConsolidated.length === 0) return null;

                                                        return (
                                                            <div className="mb-2">
                                                                <div className="text-xs font-bold text-emerald-600 mb-2 mt-1 flex items-center gap-1">
                                                                    <Layers className="w-3 h-3" />
                                                                    📊 Consolidado da Linha
                                                                </div>
                                                                <div className="pl-2 space-y-1">
                                                                    {visibleConsolidated.map(tag => (
                                                                        <div
                                                                            key={tag.id}
                                                                            className="flex items-center space-x-2 p-1.5 rounded hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors cursor-pointer border border-transparent hover:border-emerald-200 dark:hover:border-emerald-800 bg-emerald-50/30"
                                                                        >
                                                                            <Checkbox
                                                                                id={`tag-${tag.id}`}
                                                                                checked={!!selectedTags.find(t => t.id === tag.id)}
                                                                                onCheckedChange={() => toggleTag(tag)}
                                                                            />
                                                                            <label htmlFor={`tag-${tag.id}`} className="text-xs cursor-pointer flex-1 font-medium text-emerald-700 dark:text-emerald-300">
                                                                                {tag.nome}
                                                                            </label>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        );
                                                    })()}

                                                    {/* === EQUIPAMENTOS (NESTED ACCORDION) === */}
                                                    <Accordion type="multiple" className="w-full">
                                                        {linha.equipamentos.map(eq => {
                                                            const tags = getEquipmentTags(linha, eq);
                                                            const visibleTags = searchTerm
                                                                ? tags.filter(t => filterMatch(t.nome) || filterMatch(eq.nome))
                                                                : tags;

                                                            if (searchTerm && visibleTags.length === 0) return null;

                                                            return (
                                                                <AccordionItem key={eq.id} value={`eq-${eq.id}`} className="border-none">
                                                                    <AccordionTrigger className="py-2 hover:no-underline text-xs font-bold text-gray-500">
                                                                        <div className="flex items-center gap-2 text-left">
                                                                            <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0"></div>
                                                                            {eq.nome}
                                                                        </div>
                                                                    </AccordionTrigger>
                                                                    <AccordionContent className="pt-0 pb-2">
                                                                        <div className="pl-3 space-y-1">
                                                                            {visibleTags.map(tag => (
                                                                                <div
                                                                                    key={tag.id}
                                                                                    className="flex items-center space-x-2 p-1.5 rounded hover:bg-white dark:hover:bg-slate-800 transition-colors cursor-pointer border border-transparent hover:border-slate-200 dark:hover:border-slate-700 bg-white/50"
                                                                                >
                                                                                    <Checkbox
                                                                                        id={`tag-${tag.id}`}
                                                                                        checked={!!selectedTags.find(t => t.id === tag.id)}
                                                                                        onCheckedChange={() => toggleTag(tag)}
                                                                                    />
                                                                                    <label htmlFor={`tag-${tag.id}`} className="text-xs cursor-pointer flex-1 font-medium text-slate-700 dark:text-slate-300 truncate" title={tag.nome}>
                                                                                        {tag.nome}
                                                                                        {tag.isStandard && <Badge variant="outline" className="ml-1 text-[9px] h-3 px-1 py-0 border-blue-200 text-blue-400">Std</Badge>}
                                                                                    </label>
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    </AccordionContent>
                                                                </AccordionItem>
                                                            );
                                                        })}
                                                    </Accordion>
                                                </div>
                                            </AccordionContent>
                                        </AccordionItem>
                                    );
                                })}
                            </Accordion>
                        </ScrollArea>

                        {selectedTags.length > 0 && (
                            <button type="button" className="an__clear-btn" onClick={() => setSelectedTags([])}>
                                <Trash2 className="w-3 h-3" /> Limpar seleção
                            </button>
                        )}
                    </CardContent>
                </Card>

                {/* ── Área principal ── */}
                <div className="an__main">
                    {/* Note explicativo do EDA correto — POC */}
                    <Note>
                        <b>Analytics v2:</b> range datetime estilo Grafana, tratamento de contadores acumulados
                        (delta) e máscara de OFF (equipamento desligado não polui as estatísticas).
                    </Note>

                    {/* TimeRangePicker — substitui os tempos fixos antigos (1h/4h/8h/24h/7d).
                        extraRight injeta switches que SÓ fazem sentido no Trend:
                          - Live: refetch automático a cada 10s com janela deslizante.
                          - Anomalies: destaca pontos > 3σ.
                          - Trendline: regressão linear overlay para ver drift. */}
                    <TimeRangePicker
                        value={tr}
                        onChange={setTr}
                        showAnalyticsSwitches
                        ignoreOff={ignoreOff}
                        delta={applyDelta}
                        onIgnoreOffChange={setIgnoreOff}
                        onDeltaChange={setApplyDelta}
                        onRefresh={runAllAnalyses}
                        loading={loading}
                        extraRight={
                            (activeTab === 'trend' || activeTab === 'spc') ? (
                                <div className="isa-switches" style={{ marginLeft: 0 }}>
                                    <label className="isa-switch" title="Atualiza dados a cada 10s">
                                        <input type="checkbox" checked={liveMode} onChange={e => setLiveMode(e.target.checked)} />
                                        Live (10s)
                                    </label>
                                    {activeTab === 'trend' && (
                                        <>
                                            <label className="isa-switch" title="Destaca pontos > 3σ em vermelho">
                                                <input type="checkbox" checked={showAnomalies} onChange={e => setShowAnomalies(e.target.checked)} />
                                                Anomalias
                                            </label>
                                            <label className="isa-switch" title="Sobrepõe linha de regressão linear">
                                                <input type="checkbox" checked={showTrendline} onChange={e => setShowTrendline(e.target.checked)} />
                                                Trendline
                                            </label>
                                        </>
                                    )}
                                </div>
                            ) : undefined
                        }
                    />

                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full h-full flex flex-col">
                        <div className="an__tabs-bar">
                            <TabsList className="an__tabs-list">
                                <TabsTrigger value="stats"       className="an__tab"><BarChart2  className="h-3.5 w-3.5" /> Stats</TabsTrigger>
                                <TabsTrigger value="boxplot"     className="an__tab"><Box        className="h-3.5 w-3.5" /> Boxplot</TabsTrigger>
                                <TabsTrigger value="trend"       className="an__tab"><TrendingUp className="h-3.5 w-3.5" /> Tendência</TabsTrigger>
                                <TabsTrigger value="spc"         className="an__tab"><Activity   className="h-3.5 w-3.5" /> SPC</TabsTrigger>
                                <TabsTrigger value="scatter"     className="an__tab"><ScatterIcon className="h-3.5 w-3.5" /> Dispersão</TabsTrigger>
                                <TabsTrigger value="correlation" className="an__tab"><Grid       className="h-3.5 w-3.5" /> Correlação</TabsTrigger>
                            </TabsList>
                        </div>

                        {/* TABS CONTENT (Reused) */}
                        <TabsContent value="stats" className="space-y-4">
                            {statsData.map((res, idx) => {
                                const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === res.variable);
                                const isDiscrete = tagMatch?.isDiscrete || res.is_discrete;
                                const mapping = tagMatch?.valueMapping;

                                // Stats grid POC — n / Média / Std / p50 / p90 / p99
                                // Backend pode mandar `quantiles` ou só `mean/std/count` — calculamos
                                // localmente o que faltar a partir do histograma como fallback.
                                let p50: number | null = null, p90: number | null = null, p99: number | null = null;
                                if (res.stats?.quantiles) {
                                    p50 = res.stats.quantiles['0.5'] ?? res.stats.quantiles.p50 ?? null;
                                    p90 = res.stats.quantiles['0.9'] ?? res.stats.quantiles.p90 ?? null;
                                    p99 = res.stats.quantiles['0.99'] ?? res.stats.quantiles.p99 ?? null;
                                }

                                return (
                                <Card key={idx}>
                                    <CardHeader>
                                        <CardTitle>{res.variable}</CardTitle>
                                        {res.error ? (
                                            <div className="text-red-500 text-sm font-medium bg-red-50 p-2 rounded border border-red-200 dark:bg-red-900/20 dark:border-red-800">
                                                {res.error === 'No data found' ? 'Sem dados para o período selecionado' : res.error}
                                            </div>
                                        ) : !isDiscrete ? (
                                            <StatsGrid stats={[
                                                { label: 'n (amostras)', value: res.stats?.count ?? '—' },
                                                { label: 'Média',        value: numFmt.num(res.stats?.mean) },
                                                { label: 'Desvio padrão',value: numFmt.num(res.stats?.std) },
                                                { label: 'p50',          value: numFmt.num(p50) },
                                                { label: 'p90',          value: numFmt.num(p90) },
                                                { label: 'Cpk',          value: res.stats?.cpk !== undefined && res.stats.cpk !== null
                                                    ? <span style={{ color: res.stats.cpk < 1.33 ? 'var(--isa-bad)' : 'var(--isa-ok)' }}>{res.stats.cpk.toFixed(2)}</span>
                                                    : '—' },
                                            ]} />
                                        ) : (
                                            <div className="flex gap-4 text-sm text-gray-500">
                                                <span>Valores Únicos: {res.n_unique || res.stats?.count || 'N/A'}</span>
                                                <span>Contagem Total: {res.stats?.count || 'N/A'}</span>
                                            </div>
                                        )}
                                    </CardHeader>
                                    <CardContent>
                                        {!res.error && res.histogram && (() => {
                                            const bins: number[] = res.histogram.bins;
                                            const counts: number[] = res.histogram.counts;

                                            if (isDiscrete) {
                                                const colors = bins.map(val => mapping?.[val]?.color || '#3b82f6');
                                                const labels = bins.map(val => mapping?.[val]?.label || `Valor: ${val}`);

                                                return (
                                                    <Plot
                                                        data={[{
                                                            x: labels,
                                                            y: counts,
                                                            type: 'bar',
                                                            name: 'Frequência',
                                                            marker: { color: colors, line: { color: colors, width: 1 } }
                                                        }]}
                                                        layout={{
                                                            height: 320,
                                                            autosize: true,
                                                            title: { text: 'Distribuição de Frequência' },
                                                            bargap: 0.2,
                                                            xaxis: { title: { text: 'Estado/Categoria' } },
                                                            yaxis: { title: { text: 'Contagem' } }
                                                        }}
                                                        useResizeHandler={true}
                                                        className="w-full"
                                                    />
                                                );
                                            }

                                            // Continuous format
                                            const mean: number = res.stats?.mean ?? 0;
                                            const std: number = res.stats?.std ?? 1;
                                            const n: number = res.stats?.count ?? 1;
                                            const binWidth = bins.length > 1 ? bins[1] - bins[0] : 1;
                                            // Gera curva normal usando os centros dos bins
                                            const xCurve = bins.slice(0, -1).map(b => b + binWidth / 2);
                                            const yCurve = xCurve.map((x: number) =>
                                                n * binWidth * (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * ((x - mean) / std) ** 2)
                                            );
                                            return (
                                                <Plot
                                                    data={[
                                                        {
                                                            x: bins,
                                                            y: counts,
                                                            type: 'bar',
                                                            name: 'Frequência',
                                                            marker: { color: 'rgba(59,130,246,0.6)', line: { color: 'rgba(59,130,246,1)', width: 1 } }
                                                        },
                                                        {
                                                            x: xCurve,
                                                            y: yCurve,
                                                            type: 'scatter',
                                                            mode: 'lines',
                                                            name: 'Dist. Normal',
                                                            line: { color: 'red', width: 2, dash: 'dash' }
                                                        }
                                                    ]}
                                                    layout={{
                                                        height: 320,
                                                        autosize: true,
                                                        title: { text: 'Histograma com Distribuição Normal' },
                                                        bargap: 0.05,
                                                        legend: { orientation: 'h', y: -0.2 },
                                                        xaxis: { title: { text: 'Valor' } },
                                                        yaxis: { title: { text: 'Frequência' } }
                                                    }}
                                                    useResizeHandler={true}
                                                    className="w-full"
                                                />
                                            );
                                        })()}
                                    </CardContent>
                                </Card>
                            )})}
                            {statsData.length === 0 && !loading && (
                                <div className="flex items-center justify-center h-64 border-2 border-dashed rounded-lg text-gray-400">
                                    Selecione variáveis na árvore e clique em Analisar
                                </div>
                            )}
                        </TabsContent>

                        {/* === BOXPLOT TAB === */}
                        <TabsContent value="boxplot">
                            {timeseriesData ? (
                                <div className="space-y-4">
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="flex items-center gap-2">
                                                <Box className="h-5 w-5 text-purple-600" />
                                                Análise de Distribuição (Boxplot)
                                            </CardTitle>
                                            <CardDescription>
                                                Visualização de quartis, mediana e outliers para cada variável selecionada
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <Plot
                                                data={Object.entries(timeseriesData).map(([alias, d]: [string, any]) => ({
                                                    y: d.values,
                                                    type: 'box',
                                                    name: alias.split(' - ').pop() || alias, // Usar nome curto
                                                    boxpoints: 'outliers',
                                                    jitter: 0.3,
                                                    pointpos: -1.8,
                                                    marker: { size: 4, opacity: 0.6 },
                                                    hovertext: alias
                                                }))}
                                                layout={{
                                                    title: { text: 'Comparação de Distribuições' },
                                                    autosize: true,
                                                    height: 500,
                                                    showlegend: true,
                                                    boxmode: 'group',
                                                    yaxis: { title: { text: 'Valor' } }
                                                }}
                                                useResizeHandler={true}
                                                className="w-full"
                                            />
                                        </CardContent>
                                    </Card>

                                    {/* Boxplots individuais */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {Object.entries(timeseriesData).map(([alias, d]: [string, any]) => (
                                            <Card key={alias} className="border-l-4 border-l-purple-500">
                                                <CardHeader className="pb-2">
                                                    <CardTitle className="text-sm truncate" title={alias}>{alias}</CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <Plot
                                                        data={[{
                                                            y: d.values,
                                                            type: 'box',
                                                            name: 'Distribuição',
                                                            boxpoints: 'all',
                                                            jitter: 0.5,
                                                            pointpos: 0,
                                                            marker: { color: 'rgb(107, 70, 193)', size: 4, opacity: 0.5 },
                                                            line: { color: 'rgb(107, 70, 193)' },
                                                            fillcolor: 'rgba(107, 70, 193, 0.3)'
                                                        }]}
                                                        layout={{
                                                            autosize: true,
                                                            height: 250,
                                                            margin: { l: 40, r: 20, t: 20, b: 30 },
                                                            showlegend: false
                                                        }}
                                                        useResizeHandler={true}
                                                        className="w-full"
                                                    />
                                                    <div className="flex justify-between text-xs text-gray-500 mt-2">
                                                        <span>Min: {d.values.length > 0 ? Math.min(...d.values).toFixed(2) : 'N/A'}</span>
                                                        <span>Mediana: {d.values.length > 0 ? d.values.sort((a: number, b: number) => a - b)[Math.floor(d.values.length / 2)]?.toFixed(2) : 'N/A'}</span>
                                                        <span>Max: {d.values.length > 0 ? Math.max(...d.values).toFixed(2) : 'N/A'}</span>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-lg text-gray-400 gap-2">
                                    <Box className="h-8 w-8 opacity-50" />
                                    <span>Clique em "Gerar Gráficos" para visualizar os Boxplots</span>
                                </div>
                            )}
                        </TabsContent>

                        <TabsContent value="trend">
                            {timeseriesData ? (
                                <div className="space-y-4">
                                    {/* Insights cards — descobertas automáticas */}
                                    {(() => {
                                        const insights = computeInsights(timeseriesData, selectedTags);
                                        if (insights.length === 0) return null;
                                        return (
                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 8 }}>
                                                {insights.slice(0, 8).map((ins, i) => (
                                                    <div key={i} style={{
                                                        padding: '10px 12px',
                                                        borderLeft: `3px solid ${ins.tone === 'bad' ? 'var(--isa-bad)' : ins.tone === 'warn' ? 'var(--isa-warn)' : 'var(--isa-ok)'}`,
                                                        background: 'var(--isa-bg-panel)',
                                                        border: '1px solid var(--isa-border)',
                                                        borderRadius: 'var(--isa-radius)',
                                                        fontSize: 'var(--isa-fs-body)',
                                                    }}>
                                                        <div style={{ fontWeight: 600, color: ins.tone === 'bad' ? 'var(--isa-bad)' : ins.tone === 'warn' ? 'var(--isa-warn)' : 'var(--isa-ok)', marginBottom: 2 }}>
                                                            {ins.title}
                                                        </div>
                                                        <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)' }}>
                                                            {ins.desc}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        );
                                    })()}
                                    <div className="flex justify-end">
                                        <Button onClick={addChart} variant="outline" size="sm" className="gap-2">
                                            <Plus className="h-4 w-4" /> Adicionar Gráfico
                                        </Button>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {trendCharts.map((chart, index) => (
                                            <Card key={chart.id} className="col-span-1 md:col-span-2 lg:col-span-1 shadow-md hover:shadow-lg transition-all border-l-4 border-l-emerald-500">
                                                <CardHeader className="flex flex-row items-center justify-between pb-2">
                                                    <CardTitle className="text-sm font-medium">{chart.name}</CardTitle>
                                                    <div className="flex items-center gap-2">
                                                        <Popover>
                                                            <PopoverTrigger asChild>
                                                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0"><Settings className="h-4 w-4" /></Button>
                                                            </PopoverTrigger>
                                                            <PopoverContent className="w-64 p-2" align="end">
                                                                <div className="flex flex-col gap-2 mb-2">
                                                                    <Label htmlFor={`name-${chart.id}`} className="text-xs font-semibold text-gray-500">Nome do Painel</Label>
                                                                    <Input id={`name-${chart.id}`} value={chart.name} onChange={(e) => updateChartName(chart.id, e.target.value)} className="h-7 text-sm" />
                                                                </div>
                                                                <div className="mb-2 font-medium text-xs text-gray-500 mt-2">Variáveis neste gráfico</div>
                                                                <ScrollArea className="h-40 border rounded bg-slate-50 dark:bg-slate-900/50">
                                                                    {Object.keys(timeseriesData).map(alias => (
                                                                        <div key={alias} className="flex items-center space-x-2 py-1 px-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded cursor-pointer" onClick={() => toggleChartVariable(chart.id, alias)}>
                                                                            <Checkbox checked={chart.selectedAliases.includes(alias)} onCheckedChange={() => toggleChartVariable(chart.id, alias)} />
                                                                            <span className="text-xs truncate" title={alias}>{alias}</span>
                                                                        </div>
                                                                    ))}
                                                                </ScrollArea>
                                                            </PopoverContent>
                                                        </Popover>
                                                        {trendCharts.length > 1 && (
                                                            <Button onClick={() => removeChart(chart.id)} variant="ghost" size="sm" className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20">
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                    </div>
                                                </CardHeader>
                                                <CardContent>
                                                    {chart.selectedAliases.length > 0 ? (
                                                        <Plot
                                                            data={chart.selectedAliases.flatMap((alias: string, idx: number) => {
                                                                const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias);
                                                                const isDiscrete = tagMatch?.isDiscrete;
                                                                // re-ordena por timestamp antes do plot (defesa em profundidade)
                                                                const sorted = sortByTimestamp(
                                                                    timeseriesData[alias]?.timestamps,
                                                                    timeseriesData[alias]?.values,
                                                                );
                                                                const yaxisKey = idx === 0 ? 'y' : `y${idx + 1}`;
                                                                const baseTrace: any = {
                                                                    x: sorted.x,
                                                                    y: sorted.y,
                                                                    type: 'scatter',
                                                                    mode: 'lines',
                                                                    line: { shape: isDiscrete ? 'hv' : 'linear', width: 1.6 },
                                                                    name: alias.split(' - ').pop() || alias,
                                                                    hovertext: alias,
                                                                    yaxis: yaxisKey,
                                                                };
                                                                const traces: any[] = [baseTrace];

                                                                // ── Anomaly markers (>3σ) ────────────────────────────
                                                                // Heurística Shewhart: pontos > média ± 3σ são "fora de controle".
                                                                // Útil para o cientista de dados localizar EVENTOS visualmente.
                                                                if (showAnomalies && !isDiscrete && sorted.y.length > 5) {
                                                                    const nums = (sorted.y as number[]).filter(v => typeof v === 'number' && !isNaN(v));
                                                                    if (nums.length > 1) {
                                                                        const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
                                                                        const std = Math.sqrt(nums.reduce((a, b) => a + (b - mean) ** 2, 0) / nums.length);
                                                                        const ucl = mean + 3 * std;
                                                                        const lcl = mean - 3 * std;
                                                                        const anomX: any[] = [];
                                                                        const anomY: any[] = [];
                                                                        sorted.y.forEach((v: any, i: number) => {
                                                                            if (typeof v === 'number' && (v > ucl || v < lcl)) {
                                                                                anomX.push(sorted.x[i]);
                                                                                anomY.push(v);
                                                                            }
                                                                        });
                                                                        if (anomX.length > 0) {
                                                                            traces.push({
                                                                                x: anomX, y: anomY,
                                                                                type: 'scatter', mode: 'markers',
                                                                                marker: { color: '#b53a2b', size: 9, symbol: 'circle-open', line: { width: 2 } },
                                                                                name: `Anomalia (>3σ) — ${alias.split(' - ').pop()}`,
                                                                                yaxis: yaxisKey,
                                                                                showlegend: false,
                                                                                hovertemplate: '<b>Anomalia</b><br>%{x}<br>%{y:.3f}<extra></extra>',
                                                                            });
                                                                        }
                                                                    }
                                                                }

                                                                // ── Trendline (regressão linear) ─────────────────────
                                                                // Útil pra ver DRIFT: se a média está "subindo lentamente"
                                                                // ao longo do tempo, a trendline aparece inclinada.
                                                                if (showTrendline && !isDiscrete && sorted.y.length > 2) {
                                                                    const xNum: number[] = (sorted.x as string[]).map(t => new Date(t).getTime());
                                                                    const yNum: number[] = (sorted.y as any[]).map(v => Number(v));
                                                                    const reg = calcLinearRegression(xNum, yNum);
                                                                    if (reg) {
                                                                        const xLine = [reg.xMin, reg.xMax];
                                                                        const yLine = xLine.map(x => reg.slope * x + reg.intercept);
                                                                        traces.push({
                                                                            x: xLine.map(t => new Date(t).toISOString()),
                                                                            y: yLine,
                                                                            type: 'scatter', mode: 'lines',
                                                                            line: { color: '#c9932d', width: 1.5, dash: 'dash' },
                                                                            name: `Tendência ${alias.split(' - ').pop()}`,
                                                                            yaxis: yaxisKey,
                                                                            showlegend: true,
                                                                            hoverinfo: 'skip',
                                                                        });
                                                                    }
                                                                }

                                                                return traces;
                                                            })}
                                                            layout={{
                                                                title: undefined,
                                                                autosize: true,
                                                                height: 350,
                                                                margin: { l: 60, r: 60, t: 20, b: 60 },
                                                                showlegend: true,
                                                                legend: { orientation: 'h', y: -0.25 },
                                                                xaxis: { type: 'date' },
                                                                ...Object.fromEntries(
                                                                    chart.selectedAliases.map((alias: string, idx: number) => {
                                                                        const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias);
                                                                        const isDiscrete = tagMatch?.isDiscrete;
                                                                        const mapping = tagMatch?.valueMapping;
                                                                        return [
                                                                            idx === 0 ? 'yaxis' : `yaxis${idx + 1}`,
                                                                            {
                                                                                title: { text: '' },
                                                                                overlaying: idx === 0 ? undefined : 'y',
                                                                                side: idx % 2 === 0 ? 'left' : 'right',
                                                                                showgrid: idx === 0,
                                                                                autorange: true,
                                                                                ...(isDiscrete && mapping ? {
                                                                                    tickvals: Object.keys(mapping).map(Number),
                                                                                    ticktext: Object.keys(mapping).map(k => mapping[Number(k)].label),
                                                                                } : {})
                                                                            }
                                                                        ];
                                                                    })
                                                                )
                                                            } as any}
                                                            useResizeHandler={true}
                                                            className="w-full"
                                                        />
                                                    ) : (
                                                        <div className="h-[350px] flex flex-col items-center justify-center border-2 border-dashed rounded text-gray-400 gap-2">
                                                            <BarChart2 className="h-8 w-8 opacity-50" />
                                                            <span className="text-sm">Selecione variáveis nas configurações</span>
                                                        </div>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                </div>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Analisar" para visualizar.</div>}
                        </TabsContent>

                        {/* SPC — Carta de Controle Shewhart + Western Electric Rules */}
                        <TabsContent value="spc">
                            {timeseriesData ? (
                                <div className="space-y-4">
                                    {/* Insights: capability + violations */}
                                    {(() => {
                                        const insights = computeInsights(timeseriesData, selectedTags).filter(i => i.tone !== 'ok');
                                        if (insights.length === 0) return (
                                            <div style={{ padding: '10px 12px', borderLeft: '3px solid var(--isa-ok)', background: 'var(--isa-bg-panel)', border: '1px solid var(--isa-border)', borderRadius: 'var(--isa-radius)', fontSize: 'var(--isa-fs-body)' }}>
                                                <strong style={{ color: 'var(--isa-ok)' }}>Processo sob controle</strong>
                                                <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)', marginTop: 2 }}>Nenhum desvio crítico nas variáveis selecionadas.</div>
                                            </div>
                                        );
                                        return (
                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 8 }}>
                                                {insights.slice(0, 8).map((ins, i) => (
                                                    <div key={i} style={{ padding: '10px 12px', borderLeft: `3px solid ${ins.tone === 'bad' ? 'var(--isa-bad)' : 'var(--isa-warn)'}`, background: 'var(--isa-bg-panel)', border: '1px solid var(--isa-border)', borderRadius: 'var(--isa-radius)', fontSize: 'var(--isa-fs-body)' }}>
                                                        <div style={{ fontWeight: 600, color: ins.tone === 'bad' ? 'var(--isa-bad)' : 'var(--isa-warn)', marginBottom: 2 }}>{ins.title}</div>
                                                        <div style={{ color: 'var(--isa-text-muted)', fontSize: 'var(--isa-fs-meta)' }}>{ins.desc}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        );
                                    })()}

                                    {Object.entries(timeseriesData).map(([alias, d]: [string, any]) => {
                                        const tagMatch = selectedTags.find(t => `${t.linha_nome} - ${t.equipamento_nome} - ${t.nome}` === alias);
                                        const isDiscrete = tagMatch?.isDiscrete;
                                        const mapping = tagMatch?.valueMapping;
                                        if (isDiscrete) {
                                            const counts: Record<number, number> = {};
                                            d.values.forEach((v: number) => { counts[v] = (counts[v] || 0) + 1; });
                                            const x = Object.keys(counts).map(Number);
                                            const y = Object.values(counts);
                                            const colors = x.map(val => mapping?.[val]?.color || '#94a3b8');
                                            const labels = x.map(val => mapping?.[val]?.label || `Val: ${val}`);
                                            return (
                                                <Card key={alias}>
                                                    <CardHeader><CardTitle>Frequência de Estados — {alias}</CardTitle></CardHeader>
                                                    <CardContent>
                                                        <Plot data={[{ x: labels, y: y, type: 'bar', marker: { color: colors } }]} layout={{ autosize: true, height: 380, yaxis: { title: 'Registros' }, margin: { l: 50, r: 20, t: 10, b: 60 } } as any} useResizeHandler className="w-full" />
                                                    </CardContent>
                                                </Card>
                                            );
                                        }
                                        const sortedSpc = sortByTimestamp(d.timestamps, d.values);
                                        const ts = sortedSpc.x;
                                        const ys = (sortedSpc.y as number[]).filter(v => typeof v === 'number');
                                        const mean = d.stats?.mean ?? 0;
                                        const std = d.stats?.std ?? 0;
                                        const ucl = d.stats?.ucl ?? mean + 3 * std;
                                        const lcl = d.stats?.lcl ?? mean - 3 * std;
                                        const u1 = mean + std, l1 = mean - std;
                                        const u2 = mean + 2 * std, l2 = mean - 2 * std;
                                        const lsl = d.stats?.lsl, usl = d.stats?.usl;
                                        const cp = (lsl != null && usl != null && std > 0) ? (usl - lsl) / (6 * std) : null;
                                        const cpk = (lsl != null && usl != null && std > 0) ? Math.min((usl - mean) / (3 * std), (mean - lsl) / (3 * std)) : null;
                                        const violations = detectWERules(ys, mean, std);
                                        const violX: any[] = [], violY: any[] = [], violText: string[] = [];
                                        violations.forEach(v => { violX.push(sortedSpc.x[v.index]); violY.push(sortedSpc.y[v.index]); violText.push(`Regra ${v.rule}: ${v.desc}`); });
                                        return (
                                            <Card key={alias}>
                                                <CardHeader>
                                                    <CardTitle className="flex items-center justify-between">
                                                        <span>Carta de Controle — {alias}</span>
                                                        <div className="flex gap-2">
                                                            {cpk !== null && <span className="isa-tag" style={{ background: cpk < 1.33 ? 'var(--isa-bad-bg)' : 'var(--isa-ok-bg)', color: cpk < 1.33 ? 'var(--isa-bad)' : 'var(--isa-ok)' }}>Cpk {cpk.toFixed(2)}</span>}
                                                            {cp !== null && <span className="isa-tag">Cp {cp.toFixed(2)}</span>}
                                                            <span className="isa-tag" style={{ background: violations.length > 0 ? 'var(--isa-warn-bg)' : 'var(--isa-bg-muted)', color: violations.length > 0 ? 'var(--isa-warn)' : 'var(--isa-text-muted)' }}>{violations.length} violações</span>
                                                        </div>
                                                    </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <Plot
                                                        data={[
                                                            { x: ts, y: Array(ts.length).fill(u2), type: 'scatter', mode: 'lines', line: { color: 'rgba(201,147,45,0.4)', width: 0 }, showlegend: false, hoverinfo: 'skip' },
                                                            { x: ts, y: Array(ts.length).fill(ucl), type: 'scatter', mode: 'lines', name: 'UCL (+3σ)', fill: 'tonexty', fillcolor: 'rgba(201,147,45,0.10)', line: { color: 'rgba(181,58,43,0.8)', width: 1, dash: 'dash' } },
                                                            { x: ts, y: Array(ts.length).fill(u1), type: 'scatter', mode: 'lines', line: { color: 'rgba(45,134,89,0.3)', width: 0 }, showlegend: false, hoverinfo: 'skip' },
                                                            { x: ts, y: Array(ts.length).fill(l1), type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: 'rgba(45,134,89,0.08)', line: { color: 'rgba(45,134,89,0.3)', width: 0 }, showlegend: false, hoverinfo: 'skip' },
                                                            { x: ts, y: Array(ts.length).fill(l2), type: 'scatter', mode: 'lines', line: { color: 'rgba(201,147,45,0.4)', width: 0 }, showlegend: false, hoverinfo: 'skip' },
                                                            { x: ts, y: Array(ts.length).fill(lcl), type: 'scatter', mode: 'lines', name: 'LCL (-3σ)', fill: 'tonexty', fillcolor: 'rgba(201,147,45,0.10)', line: { color: 'rgba(181,58,43,0.8)', width: 1, dash: 'dash' } },
                                                            { x: ts, y: Array(ts.length).fill(mean), type: 'scatter', mode: 'lines', name: 'Média', line: { color: 'rgba(45,134,89,0.7)', width: 1, dash: 'dot' } },
                                                            { x: ts, y: sortedSpc.y, type: 'scatter', mode: 'lines+markers', name: 'Valor', line: { color: '#3f5b7c', width: 1.5 }, marker: { size: 4 } },
                                                            ...(violations.length > 0 ? [{ x: violX, y: violY, type: 'scatter' as const, mode: 'markers' as const, name: 'Violações WE', marker: { color: '#b53a2b', size: 11, symbol: 'x', line: { width: 2 } }, text: violText, hovertemplate: '<b>%{text}</b><br>%{x}<br>valor=%{y:.3f}<extra></extra>' }] : []),
                                                        ]}
                                                        layout={{ autosize: true, height: 380, margin: { l: 60, r: 30, t: 10, b: 50 }, xaxis: { type: 'date' }, showlegend: true, legend: { orientation: 'h', y: -0.18, font: { size: 10 } }, hovermode: 'x unified' } as any}
                                                        useResizeHandler
                                                        className="w-full"
                                                    />
                                                    {violations.length > 0 && (
                                                        <div style={{ marginTop: 8, maxHeight: 140, overflowY: 'auto', border: '1px solid var(--isa-border)', borderRadius: 'var(--isa-radius)', padding: 8, fontSize: 'var(--isa-fs-meta)' }}>
                                                            <strong style={{ color: 'var(--isa-bad)' }}>Western Electric Rules — pontos a investigar:</strong>
                                                            <ul style={{ listStyle: 'none', padding: 0, margin: '4px 0 0' }}>
                                                                {violations.slice(0, 10).map((v, i) => (
                                                                    <li key={i} style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
                                                                        <span style={{ fontFamily: 'var(--isa-mono)', color: 'var(--isa-text-muted)', minWidth: 110 }}>{sortedSpc.x[v.index]}</span>
                                                                        <span style={{ minWidth: 50, fontWeight: 600 }}>R{v.rule}</span>
                                                                        <span>{v.desc}</span>
                                                                    </li>
                                                                ))}
                                                                {violations.length > 10 && <li style={{ color: 'var(--isa-text-muted)', fontStyle: 'italic' }}>… e mais {violations.length - 10}</li>}
                                                            </ul>
                                                        </div>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        );
                                    })}
                                </div>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Analisar" para visualizar.</div>}
                        </TabsContent>

                        {/* Correlation tab — usa CorrMatrixPlot existente */}
                        <TabsContent value="correlation">
                            {correlationData?.correlation_matrix ? (
                                <CorrMatrixPlot
                                    matrix={correlationData.correlation_matrix}
                                    corrMinFilter={corrMinFilter}
                                    pvalToStars={pvalToStars}
                                    timeseriesData={timeseriesData}
                                    setScatterX={setScatterX}
                                    setScatterY={setScatterY}
                                    setActiveTab={setActiveTab}
                                    handleRunAnalysis={handleRunAnalysis}
                                />
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Analisar" para gerar a matriz.</div>}
                        </TabsContent>

                        {/* Scatter tab — usa ScatterPlot existente */}
                        <TabsContent value="scatter">
                            {timeseriesData ? (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Dispersão X vs Y</CardTitle>
                                        <div className="flex gap-4">
                                            <div className="w-1/2">
                                                <Label>Eixo X</Label>
                                                <Select value={scatterX} onValueChange={setScatterX}>
                                                    <SelectTrigger><SelectValue placeholder="Variável X" /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.keys(timeseriesData).map(k => <SelectItem key={k} value={k}>{k}</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="w-1/2">
                                                <Label>Eixo Y</Label>
                                                <Select value={scatterY} onValueChange={setScatterY}>
                                                    <SelectTrigger><SelectValue placeholder="Variável Y" /></SelectTrigger>
                                                    <SelectContent>
                                                        {Object.keys(timeseriesData).map(k => <SelectItem key={k} value={k}>{k}</SelectItem>)}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        {scatterX && scatterY
                                            ? <ScatterPlot xKey={scatterX} yKey={scatterY} timeseriesData={timeseriesData} calcLinearRegression={calcLinearRegression} />
                                            : <div className="p-8 text-center text-gray-500">Selecione X e Y.</div>}
                                    </CardContent>
                                </Card>
                            ) : <div className="text-center p-8 text-gray-500">Clique em "Analisar" primeiro.</div>}
                        </TabsContent>

                    </Tabs>
                </div>
            </div>

            <style>{AN_STYLES}</style>
        </div>
    );
};

const AN_STYLES = `
/* ── ISA-101 Analytics layout ── tokens vêm de styles/isa101.css ── */
.an__page { padding: 16px 20px; background: var(--isa-bg); min-height: 100vh; color: var(--isa-text); display: flex; flex-direction: column; gap: 12px; font-family: var(--isa-font); }
.an__header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; }
.an__title  { font-size: 20px; font-weight: 600; margin: 0; color: var(--isa-text); }
.an__subtitle { margin: 2px 0 0; color: var(--isa-text-muted); font-size: var(--isa-fs-default); }
.an__error  { background: var(--isa-bad-bg); border: 1px solid var(--isa-bad); color: var(--isa-bad); padding: 8px 12px; border-radius: var(--isa-radius); font-size: var(--isa-fs-default); }
.an__actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.an__btn { padding: 6px 16px; border-radius: var(--isa-radius); font-size: var(--isa-fs-default); font-weight: 500; cursor: pointer; border: 1px solid transparent; font-family: inherit; }
.an__btn:disabled { opacity: 0.55; cursor: not-allowed; }
.an__btn--primary   { background: var(--isa-accent); color: #fff; border-color: var(--isa-accent); }
.an__btn--primary:hover:not(:disabled) { background: #2f4a6a; }
.an__btn--ghost     { background: transparent; color: var(--isa-text-muted); border-color: transparent; }
.an__btn--ghost:hover:not(:disabled)     { background: var(--isa-bg-muted); }
.an__body  { display: flex; gap: 12px; flex: 1; min-height: 0; height: calc(100vh - 130px); }
.an__panel { width: 300px; flex-shrink: 0; display: flex; flex-direction: column; border: 1px solid var(--isa-border) !important; background: var(--isa-bg-panel) !important; box-shadow: none !important; border-radius: var(--isa-radius-lg) !important; }
.an__panel-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: var(--isa-text); }
.an__badge { font-size: 10px; background: var(--isa-accent-soft); color: var(--isa-accent); border: 1px solid var(--isa-accent); border-radius: 4px; padding: 1px 6px; margin-left: auto; }
.an__panel-desc { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--isa-text-muted); margin-top: 4px; }
.an__search-wrap { position: relative; }
.an__search-icon { position: absolute; left: 8px; top: 50%; transform: translateY(-50%); width: 13px; height: 13px; color: var(--isa-text-weak); pointer-events: none; }
.an__search-input { padding-left: 26px !important; height: 32px !important; font-size: 12px !important; }
.an__scroll { border: 1px solid var(--isa-border) !important; border-radius: var(--isa-radius) !important; }
.an__clear-btn { display: flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: var(--isa-radius); font-size: 11px; color: var(--isa-bad); background: var(--isa-bad-bg); border: 1px solid var(--isa-bad); cursor: pointer; }
.an__main { flex: 1; overflow: auto; display: flex; flex-direction: column; }
.an__tabs-bar { display: flex; align-items: center; gap: 8px; padding: 8px; background: var(--isa-bg-panel); border: 1px solid var(--isa-border); border-radius: var(--isa-radius-lg); margin-bottom: 10px; }
.an__tabs-list { background: var(--isa-bg-muted) !important; border-radius: var(--isa-radius) !important; padding: 3px !important; gap: 2px !important; height: auto !important; }
.an__tab { font-size: 12px !important; padding: 4px 10px !important; border-radius: 5px !important; display: flex; align-items: center; gap: 4px; height: auto !important; color: var(--isa-text-muted) !important; }
.an__tab[data-state="active"] { background: var(--isa-bg-panel) !important; color: var(--isa-text) !important; box-shadow: var(--isa-shadow-1) !important; font-weight: 600 !important; }
.an__main [class*="Card"] { border: 1px solid var(--isa-border) !important; box-shadow: var(--isa-shadow-1) !important; border-radius: var(--isa-radius-lg) !important; background: var(--isa-bg-panel) !important; }
`;

export default LineAnalytics;
