import React from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from "recharts";

interface OEEData {
  disponibilidade: number;
  performance: number;
  qualidade: number;
  oee: number;
}

interface OEEChartProps {
  data: OEEData;
  meta?: number;
  title?: string;
  showBreakdown?: boolean;
}

const getOEEColor = (value: number): string => {
  if (value >= 85) return '#10b981'; // Verde - Excelente
  if (value >= 70) return '#f59e0b'; // Amarelo - Bom
  return '#ef4444'; // Vermelho - Ruim
};

const OEEChart: React.FC<OEEChartProps> = ({
  data,
  meta = 85,
  title = "Análise OEE",
  showBreakdown = true
}) => {
  const chartData = [
    {
      name: 'Disponibilidade',
      value: data.disponibilidade,
      meta: 100,
      abbr: 'A'
    },
    {
      name: 'Performance',
      value: data.performance,
      meta: 100,
      abbr: 'P'
    },
    {
      name: 'Qualidade',
      value: data.qualidade,
      meta: 100,
      abbr: 'Q'
    },
    {
      name: 'OEE',
      value: data.oee,
      meta: meta,
      abbr: 'OEE'
    }
  ];

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-neutral-900 border border-neutral-700 rounded-lg p-3 shadow-xl">
          <p className="text-neutral-200 font-semibold mb-1">{data.name}</p>
          <p className="text-emerald-400 font-mono text-lg">
            {data.value.toFixed(1)}%
          </p>
          <p className="text-neutral-500 text-xs mt-1">
            Meta: {data.meta}%
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-neutral-200">{title}</h3>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
            <span className="text-neutral-400">≥85% Excelente</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <span className="text-neutral-400">70-85% Bom</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span className="text-neutral-400">&lt;70% Ruim</span>
          </div>
        </div>
      </div>

      {/* OEE Principal */}
      <div className="mb-6 p-4 bg-neutral-900 rounded-lg border border-neutral-800">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-neutral-500 uppercase tracking-wider mb-1">OEE Atual</p>
            <p className="text-4xl font-bold font-mono" style={{ color: getOEEColor(data.oee) }}>
              {data.oee.toFixed(1)}%
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-neutral-500 uppercase tracking-wider mb-1">Meta</p>
            <p className="text-2xl font-semibold text-neutral-400">{meta}%</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-neutral-500 uppercase tracking-wider mb-1">Desvio</p>
            <p className={`text-2xl font-semibold ${data.oee >= meta ? 'text-emerald-400' : 'text-red-400'}`}>
              {data.oee >= meta ? '+' : ''}{(data.oee - meta).toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {/* Breakdown */}
      {showBreakdown && (
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-neutral-400 uppercase tracking-wider">Breakdown OEE</h4>
          
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#404040" />
              <XAxis 
                dataKey="abbr" 
                stroke="#737373"
                tick={{ fill: '#a3a3a3', fontSize: 12 }}
              />
              <YAxis 
                stroke="#737373"
                tick={{ fill: '#a3a3a3', fontSize: 12 }}
                domain={[0, 100]}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }} />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getOEEColor(entry.value)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Fórmula OEE */}
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Cálculo OEE</p>
            <div className="flex items-center justify-center gap-2 text-sm font-mono">
              <span className="text-emerald-400">{data.disponibilidade.toFixed(1)}%</span>
              <span className="text-neutral-600">×</span>
              <span className="text-blue-400">{data.performance.toFixed(1)}%</span>
              <span className="text-neutral-600">×</span>
              <span className="text-purple-400">{data.qualidade.toFixed(1)}%</span>
              <span className="text-neutral-600">=</span>
              <span className="text-white font-bold">{data.oee.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OEEChart;
