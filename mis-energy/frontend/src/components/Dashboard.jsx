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
              return { id: eq.id, value: data.data.value, unit: data.data.unit, success: true };
            }
            return { id: eq.id, success: false, error: data.error };
          } catch {
            return { id: eq.id, success: false };
          }
        })
      );

      // Update equipment with new values
      setEquipments(prev => prev.map(eq => {
        const update = updates.find(u => u.id === eq.id);
        if (update?.success) {
          return { ...eq, last_value: update.value, unit: update.unit, read_success: true };
        }
        return { ...eq, read_success: false };
      }));

      setLastUpdate(new Date());
    } catch (error) {
      console.error("Error fetching real-time values:", error);
    } finally {
      setRefreshing(false);
    }
  }, [equipments.length]);

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

  // Handle date range change
  const handleDateRangeChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
    // Trigger data refresh with new date range
  };

  // Equipment Card Component
  const EquipmentCard = ({ equipment }) => {
    const isAboveStandard = equipment.standard_consumption &&
      equipment.last_value > equipment.standard_consumption;
    const isRunning = equipment.is_active;
    const consumptionPercent = equipment.standard_consumption
      ? (equipment.last_value / equipment.standard_consumption) * 100
      : 50;

    return (
      <Card
        className={`cursor-pointer transition-all hover:shadow-lg ${selectedEquipment?.id === equipment.id
            ? 'ring-2 ring-blue-500 shadow-lg'
            : ''
          }`}
        onClick={() => setSelectedEquipment(equipment)}
      >
        <CardContent className="p-4">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-lg ${equipment.meter_type === 'energy'
                  ? 'bg-blue-100 dark:bg-blue-900/30'
                  : 'bg-green-100 dark:bg-green-900/30'
                }`}>
                <Zap className={`h-4 w-4 ${equipment.meter_type === 'energy'
                    ? 'text-blue-600'
                    : 'text-green-600'
                  }`} />
              </div>
              <Badge
                variant={isRunning ? 'default' : 'secondary'}
                className={isRunning ? 'bg-green-500' : ''}
              >
                {isRunning ? 'Online' : 'Offline'}
              </Badge>
            </div>
            {equipment.read_success === false && (
              <AlertCircle className="h-4 w-4 text-amber-500" />
            )}
          </div>

          {/* Name */}
          <h4 className="font-semibold text-slate-900 dark:text-white truncate mb-1">
            {equipment.name}
          </h4>
          <p className="text-xs text-slate-500 truncate mb-3">
            {equipment.hierarchy_path || 'Sem localização'}
          </p>

          {/* Current Value - Large Display */}
          <div className={`p-3 rounded-lg mb-3 ${isAboveStandard
              ? 'bg-red-50 dark:bg-red-900/20 border border-red-200'
              : 'bg-green-50 dark:bg-green-900/20 border border-green-200'
            }`}>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600 dark:text-slate-400">Valor Atual</span>
              {isAboveStandard ? (
                <TrendingUp className="h-4 w-4 text-red-500" />
              ) : (
                <TrendingDown className="h-4 w-4 text-green-500" />
              )}
            </div>
            <p className={`text-2xl font-bold ${isAboveStandard ? 'text-red-600' : 'text-green-600'
              }`}>
              {equipment.last_value != null
                ? Number(equipment.last_value).toLocaleString('pt-BR', { maximumFractionDigits: 2 })
                : '--'}
              <span className="text-sm font-normal ml-1">{equipment.unit || 'kWh'}</span>
            </p>
          </div>

          {/* Standard vs Actual Progress */}
          {equipment.standard_consumption && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-500">
                <span>Consumo Padrão: {equipment.standard_consumption} {equipment.unit}</span>
                <span>{consumptionPercent.toFixed(0)}%</span>
              </div>
              <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${consumptionPercent > 100 ? 'bg-red-500' : 'bg-green-500'
                    }`}
                  style={{ width: `${Math.min(consumptionPercent, 100)}%` }}
                />
              </div>
            </div>
          )}
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
    <div className="flex h-[calc(100vh-80px)] gap-4 p-4 bg-slate-50/50 dark:bg-slate-950/50">
      {/* Sidebar - Hierarchy Navigation */}
      <div className="w-80 flex-shrink-0 flex flex-col bg-white dark:bg-slate-900 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b bg-slate-50 dark:bg-slate-800/50">
          <h3 className="font-semibold flex items-center text-slate-700 dark:text-slate-200">
            <ListTree className="h-4 w-4 mr-2" />
            Navegação
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <HierarchyManager
            onSelect={(node) => setSelectedNode(node)}
            selectedId={selectedNode?.id}
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-4 overflow-hidden">
        {/* Header with Controls */}
        <div className="flex items-center justify-between bg-white dark:bg-slate-900 rounded-xl p-4 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              {selectedNode ? selectedNode.name : 'Todos os Medidores'}
            </h1>
            <p className="text-sm text-slate-500">
              {totalEquipments} medidores • {onlineCount} online
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

            <div className="text-xs text-slate-400">
              Atualizado: {lastUpdate.toLocaleTimeString()}
            </div>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-3 rounded-xl bg-blue-100 dark:bg-blue-900/30">
                <Zap className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Consumo Total</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {totalConsumption.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} kWh
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-3 rounded-xl bg-green-100 dark:bg-green-900/30">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Online</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {onlineCount} / {totalEquipments}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-3 rounded-xl bg-red-100 dark:bg-red-900/30">
                <AlertCircle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Acima do Padrão</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {aboveStandardCount}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="p-3 rounded-xl bg-purple-100 dark:bg-purple-900/30">
                <Activity className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Média/Medidor</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white">
                  {totalEquipments > 0
                    ? (totalConsumption / totalEquipments).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
                    : 0} kWh
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Equipment Grid */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
          ) : equipments.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {equipments.map((eq) => (
                <EquipmentCard key={eq.id} equipment={eq} />
              ))}
            </div>
          ) : (
            <Card className="h-full flex items-center justify-center border-dashed">
              <div className="text-center text-slate-400">
                <LayoutDashboard className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium">Nenhum medidor encontrado</p>
                <p className="text-sm">Selecione um nível na hierarquia</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
