import { useState, useEffect } from 'react';
import api from '../services/api';
import { FactoryOverview } from './Dashboard/FactoryOverview';
import { EquipmentDetail } from './Dashboard/EquipmentDetail';
import { HierarchyManager } from './HierarchyManager';
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LayoutDashboard, ListTree, Loader2 } from "lucide-react";

export function Dashboard() {
  const [overviewData, setOverviewData] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedEquipment, setSelectedEquipment] = useState(null);
  const [equipmentHistory, setEquipmentHistory] = useState([]);
  const [equipmentStats, setEquipmentStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Equipment list for selected hierarchy node
  const [nodeEquipments, setNodeEquipments] = useState([]);
  const [loadingEquipments, setLoadingEquipments] = useState(false);

  // Fetch Overview Data
  useEffect(() => {
    const fetchOverview = async () => {
      try {
        const query = selectedNode ? `?hierarchy_id=${selectedNode.id}` : '';
        const data = await api.get(`/analytics/overview${query}`);
        if (data.success) {
          setOverviewData(data.data);
        }
      } catch (error) {
        console.error("Error fetching overview:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchOverview();
    const interval = setInterval(fetchOverview, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [selectedNode]);

  // Fetch Equipment list when hierarchy node is selected
  useEffect(() => {
    if (!selectedNode) {
      setNodeEquipments([]);
      return;
    }

    const fetchNodeEquipments = async () => {
      setLoadingEquipments(true);
      try {
        const data = await api.get(`/equipments?hierarchy_id=${selectedNode.id}`);
        if (data.success) {
          setNodeEquipments(data.data);
        } else {
          setNodeEquipments([]);
        }
      } catch (error) {
        console.error("Error fetching node equipments:", error);
        setNodeEquipments([]);
      } finally {
        setLoadingEquipments(false);
      }
    };

    fetchNodeEquipments();
  }, [selectedNode]);

  // Fetch Equipment Details when selected
  useEffect(() => {
    if (!selectedEquipment) return;

    const fetchDetails = async () => {
      try {
        // Fetch History
        const histData = await api.get(`/analytics/equipment/${selectedEquipment.id}/history?hours=24`);
        if (histData.success) setEquipmentHistory(histData.data);

        // Fetch Stats
        const statsData = await api.get(`/analytics/equipment/${selectedEquipment.id}/statistics?hours=24`);
        if (statsData.success) setEquipmentStats(statsData.data.statistics);

      } catch (error) {
        console.error("Error fetching equipment details:", error);
      }
    };

    fetchDetails();
  }, [selectedEquipment]);

  return (
    <div className="space-y-6 p-6 bg-slate-50/50 dark:bg-slate-950/50 min-h-screen">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">Dashboard Industrial</h1>
          <p className="text-slate-500 mt-1">Visão geral da eficiência e monitoramento em tempo real</p>
        </div>
        <div className="text-sm text-slate-400">
          Última atualização: {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* Factory Overview Cards */}
      <FactoryOverview data={overviewData} />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mt-6">
        {/* Sidebar: Hierarchy Navigation */}
        <Card className="lg:col-span-1 h-[calc(100vh-300px)] overflow-hidden flex flex-col">
          <div className="p-4 border-b bg-slate-50 dark:bg-slate-900/50">
            <h3 className="font-semibold flex items-center text-slate-700 dark:text-slate-200">
              <ListTree className="h-4 w-4 mr-2" />
              Navegação
            </h3>
          </div>
          <CardContent className="flex-1 overflow-y-auto p-2">
            <HierarchyManager
              onSelect={(node) => {
                setSelectedNode(node);
                setSelectedEquipment(null); // Clear selection when changing node
              }}
              selectedId={selectedNode?.id}
            />

            {/* Dynamic Equipment List from API */}
            {selectedNode && (
              <div className="mt-4 pt-4 border-t">
                <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wider">
                  Equipamentos em {selectedNode.name}
                </p>
                <div className="space-y-1">
                  {loadingEquipments ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                    </div>
                  ) : nodeEquipments.length > 0 ? (
                    nodeEquipments.map((eq) => (
                      <button
                        key={eq.id}
                        onClick={() => setSelectedEquipment(eq)}
                        className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${selectedEquipment?.id === eq.id
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                            : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                          }`}
                      >
                        {eq.name}
                      </button>
                    ))
                  ) : (
                    <p className="text-xs text-slate-400 italic py-2">
                      Nenhum equipamento neste nível
                    </p>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Main Content: Equipment Detail */}
        <div className="lg:col-span-3">
          {selectedEquipment ? (
            <EquipmentDetail
              equipment={selectedEquipment}
              history={equipmentHistory}
              statistics={equipmentStats}
            />
          ) : (
            <Card className="h-full flex items-center justify-center bg-slate-50/50 border-dashed">
              <div className="text-center text-slate-400">
                <LayoutDashboard className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium">Selecione um equipamento para ver detalhes</p>
                <p className="text-sm">Use a navegação à esquerda para explorar a fábrica</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
