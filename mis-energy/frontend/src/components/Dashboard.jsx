import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { HierarchyManager } from './HierarchyManager';
import { DateRangePicker } from './ui/DateRangePicker';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  LayoutDashboard, ListTree, Loader2, Zap, Activity, TrendingUp,
  TrendingDown, RefreshCw, AlertCircle, CheckCircle
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

export function Dashboard() {
  // State
  const [selectedNode, setSelectedNode] = useState(null);
  const [equipments, setEquipments] = useState([]);
  const [selectedEquipment, setSelectedEquipment] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // Date range state
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setHours(d.getHours() - 12);
    return d;
  });
  const [endDate, setEndDate] = useState(new Date());

  // Equipment history for charts
  const [equipmentHistory, setEquipmentHistory] = useState({});

  // Fetch equipment based on selected hierarchy (recursive)
  const fetchEquipments = useCallback(async (hierarchyId = null) => {
    setLoading(true);
    try {
      let url = '/equipments';
      if (hierarchyId) {
        url += `?hierarchy_id=${hierarchyId}&recursive=true`;
      }
      const data = await api.get(url);
      if (data.success) {
        setEquipments(data.data);
      }
    } catch (error) {
      console.error("Error fetching equipments:", error);
      setEquipments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch real-time values for all visible equipment
  const fetchRealTimeValues = useCallback(async () => {
    if (equipments.length === 0) return;

    setRefreshing(true);
    try {
      // Fetch current values for each equipment
      const updates = await Promise.all(
        equipments.map(async (eq) => {
          try {
            const data = await api.post(`/equipments/${eq.id}/read`, {}, { timeout: 10000 });
            if (data.success) {
              return {
                id: eq.id,
                success: true,
                newValues: {
                  last_value: data.data.value,
                  unit: data.data.unit,
                  efficiency_kwh_ton: data.data.efficiency_kwh_ton, // Now included in /read response
                  last_reading_at: data.data.timestamp
                }
              };
            }
            return { id: eq.id, success: false, error: 'Failed' };
          } catch (e) {
            return { id: eq.id, success: false, error: String(e) };
          }
        })
      );

      // Update equipment with new values
      setEquipments(prev => prev.map(eq => {
        const update = updates.find(u => u.id === eq.id);
        if (update?.success) {
          return { ...eq, ...update.newValues, read_success: true };
        }
        return { ...eq, read_success: false };
      }));

      setLastUpdate(new Date());
    } catch (error) {
      console.error("Error fetching real-time values:", error);
    } finally {
      setRefreshing(false);
    }
  }, [equipments]);

  // Initial load - fetch all equipment
  useEffect(() => {
    fetchEquipments();
  }, []);

  // When hierarchy selection changes
  useEffect(() => {
    if (selectedNode) {
      // Check if it's an equipment node
      if (selectedNode.type === 'equipment') {
        fetchEquipments(selectedNode.parent_id || null);
        setSelectedEquipment(selectedNode);
      } else {
        fetchEquipments(selectedNode.id);
        setSelectedEquipment(null);
      }
    } else {
      fetchEquipments();
      setSelectedEquipment(null);
    }
  }, [selectedNode, fetchEquipments]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (!loading) {
        fetchRealTimeValues();
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchRealTimeValues, loading]);

  // Calculate period string from date range
  const getPeriodFromRange = (start, end) => {
    const diffMs = end.getTime() - start.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours <= 1) return '1h';
    if (diffHours <= 6) return '6h';
    if (diffHours <= 12) return '12h';
    if (diffHours <= 24) return '24h';
    if (diffHours <= 168) return '7d';
    return '30d';
  };

  // Selected metrics per equipment
  const [selectedMetrics, setSelectedMetrics] = useState({});

  // Fetch history for a single equipment
  const fetchSingleHistory = async (equipment, metric, period) => {
    try {
      const data = await api.get(`/equipments/${equipment.id}/history?metric=${metric}&period=${period}`);
      if (data.success && data.data.history) {
        setEquipmentHistory(prev => ({
          ...prev,
          [equipment.id]: data.data.history.map(h => ({
            v: h.value || 0,
            date: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }))
        }));
      }
    } catch (error) {
      console.error(`Error fetching history for ${equipment.name}:`, error);
    }
  };

  // Fetch historical data for all equipments
  const fetchEquipmentHistory = useCallback(async (period = '12h') => {
    if (equipments.length === 0) return;

    try {
      const historyPromises = equipments.map(async (eq) => {
        try {
          // Use selected metric or default based on type
          const metric = selectedMetrics[eq.id] || (eq.meter_type === 'production' ? 'production_rate' : 'power_kw');
          const data = await api.get(`/equipments/${eq.id}/history?metric=${metric}&period=${period}`);

          if (data.success && data.data.history) {
            return {
              id: eq.id,
              history: data.data.history.map(h => ({
                v: h.value || 0,
                date: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              }))
            };
          }
          return { id: eq.id, history: [] };
        } catch {
          return { id: eq.id, history: [] };
        }
      });

      const results = await Promise.all(historyPromises);
      const historyMap = {};
      results.forEach(r => { historyMap[r.id] = r.history; });
      setEquipmentHistory(historyMap);
    } catch (error) {
      console.error("Error fetching equipment history:", error);
    }
  }, [equipments, selectedMetrics]);

  // Handle metric change for an equipment
  const handleMetricChange = (equipment, newMetric) => {
    setSelectedMetrics(prev => ({ ...prev, [equipment.id]: newMetric }));
    const period = getPeriodFromRange(startDate, endDate);
    fetchSingleHistory(equipment, newMetric, period);
  };

  // Fetch history when equipments change or date range changes
  useEffect(() => {
    if (equipments.length > 0) {
      const period = getPeriodFromRange(startDate, endDate);
      fetchEquipmentHistory(period);
    }
  }, [equipments.length, startDate, endDate]);

  // Handle date range change
  const handleDateRangeChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
    // History will be refetched automatically via useEffect
  };

  // Equipment Card Component - Enhanced
  const EquipmentCard = ({ equipment }) => {
    const isProduction = equipment.meter_type === 'production';
    const currentMetric = selectedMetrics[equipment.id] || (isProduction ? 'production_rate' : 'power_kw');

    const isAboveStandard = equipment.standard_consumption &&
      Number(equipment.last_value) > Number(equipment.standard_consumption);
    const isBelowStandard = equipment.standard_consumption &&
      Number(equipment.last_value) < Number(equipment.standard_consumption);
    const isRunning = equipment.is_active;

    const consumptionPercent = equipment.standard_consumption
      ? (equipment.last_value / equipment.standard_consumption) * 100
      : 50;

    // Semantic color for progress bar
    const getProgressColor = () => {
      if (isProduction) {
        if (consumptionPercent < 80) return 'bg-red-500';
        if (consumptionPercent < 100) return 'bg-amber-500';
        if (consumptionPercent <= 120) return 'bg-green-500';
        return 'bg-blue-500';
      } else {
        if (consumptionPercent < 80) return 'bg-blue-500';
        if (consumptionPercent <= 100) return 'bg-green-500';
        if (consumptionPercent <= 120) return 'bg-amber-500';
        return 'bg-red-500';
      }
    };

    // Calculate cost per hour (for energy meters)
    const costPerHour = equipment.tariff_kwh && equipment.last_value
      ? (equipment.last_value * equipment.tariff_kwh).toFixed(2)
      : null;

    // Get real trend data from history
    const historyData = equipmentHistory[equipment.id];
    const sparklineData = historyData && historyData.length > 0
      ? historyData.slice(-40)
      : [
        { v: 0, date: '' }, { v: 0, date: '' }
      ];

    // Metric Options
    const metricOptions = isProduction
      ? [
        { value: 'production_rate', label: 'Produção (Ton/h)' },
        { value: 'efficiency_kwh_ton', label: 'Eficiência (kWh/Ton)' },
        { value: 'total_production', label: 'Produção Total (Ton)' }
      ]
      : [
        { value: 'power_kw', label: 'Potência (kW)' },
        { value: 'energy_kwh', label: 'Energia (kWh)' },
        { value: 'voltage_a', label: 'Tensão (V)' },
        { value: 'current_a', label: 'Corrente (A)' },
        { value: 'power_factor', label: 'Fator de Potência' }
      ];

    return (
      <Card
        className={`cursor-pointer transition-all hover:shadow-lg hover:scale-[1.01] flex flex-col h-[380px] ${selectedEquipment?.id === equipment.id
          ? 'ring-2 ring-blue-500 shadow-xl'
          : ''
          }`}
        onClick={() => setSelectedEquipment(equipment)}
      >
        <CardContent className="p-4 flex flex-col h-full">
          {/* Header: Name + Metric Select */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0 mr-2">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant={isRunning ? 'default' : 'secondary'} className={`h-5 px-1.5 text-[10px] ${isRunning ? 'bg-green-500 hover:bg-green-600' : ''}`}>
                  {isRunning ? 'ON' : 'OFF'}
                </Badge>
                <h4 className="font-bold text-slate-800 dark:text-white truncate text-sm" title={equipment.name}>
                  {equipment.name}
                </h4>
              </div>
              <p className="text-[10px] text-slate-400 truncate flex items-center gap-1">
                {equipment.hierarchy_path || equipment.gateway?.name || 'Sem localização'}
              </p>
            </div>

            <select
              className="text-[10px] uppercase font-medium border rounded-md bg-slate-50 dark:bg-slate-800 p-1.5 h-7 max-w-[110px] text-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
              value={currentMetric}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => handleMetricChange(equipment, e.target.value)}
            >
              {metricOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Interactive Trend Chart */}
          <div className="flex-1 min-h-[120px] mb-4 relative bg-slate-50/50 dark:bg-slate-900/30 rounded-lg p-2 border border-slate-100 dark:border-slate-800/50">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sparklineData} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={`gradient-${equipment.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={isProduction ? '#22c55e' : '#3b82f6'} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={isProduction ? '#22c55e' : '#3b82f6'} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  hide={false}
                  tick={{ fontSize: 9, fill: '#94a3b8' }}
                  interval="preserveStartEnd"
                  tickMargin={8}
                  minTickGap={30}
                />
                <YAxis
                  domain={['auto', 'auto']}
                  hide={true}
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="bg-slate-800 text-white text-[10px] px-2 py-1.5 rounded shadow-xl border border-slate-700 z-50">
                          <div className="font-semibold mb-1 text-slate-300">{label}</div>
                          <div className="flex items-center gap-1">
                            <span className="font-bold text-lg">{Number(payload[0].value).toFixed(1)}</span>
                            <span className="text-slate-400">{equipment.unit || 'Val'}</span>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={isProduction ? '#22c55e' : '#3b82f6'}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 0, fill: isProduction ? '#22c55e' : '#3b82f6' }}
                  fill={`url(#gradient-${equipment.id})`}
                />
              </LineChart>
            </ResponsiveContainer>
            {/* Min/Max indicators */}
            {sparklineData.length > 1 && (
              <div className="absolute top-1 right-2 flex gap-2">
                <span className="text-[9px] text-slate-400 bg-white/90 dark:bg-slate-900/90 px-1.5 py-0.5 rounded shadow-sm border border-slate-100 dark:border-slate-800">
                  Max: {Math.max(...sparklineData.map(d => d.v)).toFixed(0)}
                </span>
                <span className="text-[9px] text-slate-400 bg-white/90 dark:bg-slate-900/90 px-1.5 py-0.5 rounded shadow-sm border border-slate-100 dark:border-slate-800">
                  Avg: {(sparklineData.reduce((a, b) => a + b.v, 0) / sparklineData.length).toFixed(0)}
                </span>
              </div>
            )}
          </div>

          {/* Metrics Grid - Compact 2x2 */}
          <div className="grid grid-cols-2 gap-3 mt-auto">
            {/* Cell 1: Current Value */}
            <div className={`p-2.5 rounded-lg border flex flex-col justify-center h-[70px] ${isProduction
              ? (isBelowStandard ? 'bg-red-50 border-red-100 dark:bg-red-900/10 dark:border-red-900/30' : 'bg-green-50 border-green-100 dark:bg-green-900/10 dark:border-green-900/30')
              : (isAboveStandard ? 'bg-red-50 border-red-100 dark:bg-red-900/10 dark:border-red-900/30' : 'bg-green-50 border-green-100 dark:bg-green-900/10 dark:border-green-900/30')
              }`}>
              <span className="text-[9px] uppercase tracking-wider text-slate-500 font-bold mb-1">Valor Atual</span>
              <div className="flex items-baseline gap-1.5">
                <span className={`text-xl font-bold leading-none ${(isProduction ? isBelowStandard : isAboveStandard) ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'
                  }`}>
                  {equipment.last_value != null ? Number(equipment.last_value).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) : '--'}
                </span>
                <span className="text-[10px] text-slate-500 font-medium">{equipment.unit}</span>
              </div>
            </div>

            {/* Cell 2: Target/Efficiency */}
            <div className="p-2.5 rounded-lg border bg-slate-50 border-slate-100 dark:bg-slate-800/30 dark:border-slate-800 flex flex-col justify-center h-[70px]">
              <span className="text-[9px] uppercase tracking-wider text-slate-500 font-bold mb-1">
                {isProduction ? 'Eficiência' : 'Custo/Hora'}
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-lg font-bold text-slate-700 dark:text-slate-300 leading-none">
                  {isProduction
                    ? (equipment.efficiency_kwh_ton ? equipment.efficiency_kwh_ton.toFixed(2) : '--')
                    : (costPerHour ? `R$ ${costPerHour}` : '--')}
                </span>
                {isProduction && <span className="text-[9px] text-slate-500 font-medium">kWh/t</span>}
              </div>
            </div>

            {/* Cell 3: Standard Bar */}
            <div className="col-span-2 p-2.5 rounded-lg border bg-white border-slate-100 dark:bg-slate-900 dark:border-slate-800 h-[50px] flex flex-col justify-center">
              <div className="flex justify-between items-end mb-1.5">
                <span className="text-[10px] text-slate-500 font-medium">Meta: {equipment.standard_consumption || '--'} {equipment.unit}</span>
                <span className={`text-[10px] font-bold ${(isProduction && consumptionPercent < 100) || (!isProduction && consumptionPercent > 100)
                  ? 'text-red-500'
                  : 'text-green-500'
                  }`}>
                  {consumptionPercent.toFixed(0)}%
                </span>
              </div>
              <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full transition-all duration-1000 ${getProgressColor()}`} style={{ width: `${Math.min(consumptionPercent, 100)}%` }} />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  // Summary Stats
  const totalEquipments = equipments.length;
  const onlineCount = equipments.filter(e => e.is_active).length;
  const totalConsumption = equipments.reduce((sum, e) => sum + (e.last_value || 0), 0);
  const aboveStandardCount = equipments.filter(e =>
    e.standard_consumption && e.last_value > e.standard_consumption
  ).length;

  return (
    <div className="flex h-[calc(100vh-80px)] gap-6 p-6 bg-slate-50/50 dark:bg-slate-950/50">
      {/* Sidebar - Hierarchy Navigation */}
      <div className="w-80 flex-shrink-0 flex flex-col bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200/50 dark:border-slate-800 overflow-hidden hidden xl:flex">
        <div className="p-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20">
          <h3 className="font-semibold flex items-center text-slate-700 dark:text-slate-200">
            <ListTree className="h-4 w-4 mr-2" />
            Navegação
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <HierarchyManager
            onSelect={(node) => setSelectedNode(node)}
            selectedId={selectedNode?.id}
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-6 overflow-hidden">
        {/* Header with Controls */}
        <div className="flex items-center justify-between bg-white dark:bg-slate-900 rounded-xl p-5 shadow-sm border border-slate-200/50 dark:border-slate-800">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {selectedNode ? selectedNode.name : 'Todos os Medidores'}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              {totalEquipments} medidores monitorados • {onlineCount} online agora
            </p>
          </div>

          <div className="flex items-center gap-3">
            <DateRangePicker
              startDate={startDate}
              endDate={endDate}
              onRangeChange={handleDateRangeChange}
            />

            <Button
              variant="outline"
              size="icon"
              onClick={fetchRealTimeValues}
              disabled={refreshing}
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="border-none shadow-sm bg-white dark:bg-slate-900">
            <CardContent className="p-5 flex items-center gap-4">
              <div className="p-3 rounded-2xl bg-blue-50 dark:bg-blue-900/20">
                <Zap className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Consumo Total</p>
                <p className="text-2xl font-bold text-slate-900 dark:text-white mt-0.5">
                  {totalConsumption.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} <span className="text-sm text-slate-400 font-normal">kWh</span>
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-none shadow-sm bg-white dark:bg-slate-900">
            <CardContent className="p-5 flex items-center gap-4">
              <div className="p-3 rounded-2xl bg-green-50 dark:bg-green-900/20">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Online</p>
                <p className="text-2xl font-bold text-slate-900 dark:text-white mt-0.5">
                  {onlineCount} <span className="text-sm text-slate-400 font-normal">/ {totalEquipments}</span>
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-none shadow-sm bg-white dark:bg-slate-900">
            <CardContent className="p-5 flex items-center gap-4">
              <div className="p-3 rounded-2xl bg-red-50 dark:bg-red-900/20">
                <AlertCircle className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Alertas</p>
                <p className="text-2xl font-bold text-slate-900 dark:text-white mt-0.5">
                  {aboveStandardCount}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-none shadow-sm bg-white dark:bg-slate-900">
            <CardContent className="p-5 flex items-center gap-4">
              <div className="p-3 rounded-2xl bg-purple-50 dark:bg-purple-900/20">
                <Activity className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Média Global</p>
                <p className="text-2xl font-bold text-slate-900 dark:text-white mt-0.5">
                  {totalEquipments > 0
                    ? (totalConsumption / totalEquipments).toLocaleString('pt-BR', { maximumFractionDigits: 0 })
                    : 0} <span className="text-sm text-slate-400 font-normal">kWh</span>
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Equipment Grid */}
        <div className="flex-1 overflow-y-auto pr-2 pb-4">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
          ) : equipments.length > 0 ? (
            <div
              className="grid gap-6"
              style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))' }}
            >
              {equipments.map((eq) => (
                <EquipmentCard key={eq.id} equipment={eq} />
              ))}
            </div>
          ) : (
            <Card className="h-60 flex items-center justify-center border-dashed bg-slate-50/50">
              <div className="text-center text-slate-400">
                <LayoutDashboard className="h-10 w-10 mx-auto mb-3 opacity-40" />
                <p className="text-lg font-medium">Nenhum medidor encontrado</p>
                <p className="text-sm">Selecione um nível na hierarquia para visualizar</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
