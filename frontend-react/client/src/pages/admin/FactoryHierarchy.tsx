import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import HierarchyTree from "../../components/admin/HierarchyTree";
import { Plus, RefreshCw } from "lucide-react";
import { Button } from "../../components/ui/button";
import { toast } from "sonner";
import { DJANGO_API_URL } from '@/config/api';

interface Equipment {
  id: number;
  nome: string;
  codigo: string;
  tipo: string;
  estado?: any;
}

interface Line {
  id: number;
  codigo: string;
  nome: string;
  equipamentos: Equipment[];
}

interface Area {
  id: number;
  codigo: string;
  nome: string;
  linhas: Line[];
}

interface Factory {
  id: number;
  codigo: string;
  nome: string;
  areas: Area[];
}

const FactoryHierarchy: React.FC = () => {

  const navigate = useNavigate();

  const [factories, setFactories] = useState<Factory[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [selectedType, setSelectedType] = useState<'factory' | 'area' | 'line' | 'equipment' | null>(null);

  const fetchHierarchy = async () => {
    setLoading(true);
    try {
      // Buscar fábricas
      const fabricasResp = await fetch(`${DJANGO_API_URL}/fabricas/`);
      const fabricasData = await fabricasResp.json();
      const fabricas = fabricasData.results || fabricasData;

      // Buscar áreas
      const areasResp = await fetch(`${DJANGO_API_URL}/areas/`);
      const areasData = await areasResp.json();
      const areas = areasData.results || areasData;

      // Buscar linhas
      const linhasResp = await fetch(`${DJANGO_API_URL}/linhas/`);
      const linhasData = await linhasResp.json();
      const linhas = linhasData.results || linhasData;

      // Buscar equipamentos
      const equipResp = await fetch(`${DJANGO_API_URL}/equipamentos/`);
      const equipData = await equipResp.json();
      const equipamentos = equipData.results || equipData;

      // Montar hierarquia
      const hierarchy: Factory[] = fabricas.map((fab: any) => {
        const fabricaAreas = areas
          .filter((area: any) => area.fabrica === fab.id)
          .map((area: any) => {
            const areaLinhas = linhas
              .filter((linha: any) => linha.area === area.id)
              .map((linha: any) => {
                const linhaEquipamentos = equipamentos
                  .filter((eq: any) => eq.linha === linha.id)
                  .map((eq: any) => ({
                    id: eq.id,
                    nome: eq.nome,
                    codigo: eq.codigo,
                    tipo: eq.tipo,
                    estado: 'RUN' // Em produção, viria do Flask API
                  }));

                return {
                  id: linha.id,
                  codigo: linha.codigo,
                  nome: linha.nome,
                  equipamentos: linhaEquipamentos
                };
              });

            return {
              id: area.id,
              codigo: area.codigo,
              nome: area.nome,
              linhas: areaLinhas
            };
          });

        return {
          id: fab.id,
          codigo: fab.codigo,
          nome: fab.nome,
          areas: fabricaAreas
        };
      });

      setFactories(hierarchy);
      setLoading(false);
    } catch (error) {
      console.error("Erro ao carregar hierarquia", error);
      toast.error("Falha ao carregar hierarquia da fábrica");
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHierarchy();
  }, []);

  const handleSelectEquipment = (equipment: Equipment) => {
    setSelectedItem(equipment);
    setSelectedType('equipment');
  };

  const handleSelectLine = (line: Line) => {
    setSelectedItem(line);
    setSelectedType('line');
  };

  const handleSelectArea = (area: Area) => {
    setSelectedItem(area);
    setSelectedType('area');
  };

  const handleSelectFactory = (factory: Factory) => {
    setSelectedItem(factory);
    setSelectedType('factory');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-neutral-400">Carregando hierarquia...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-semibold text-neutral-100">Hierarquia de Fábrica</h2>
          <p className="text-sm text-neutral-500">Estrutura ISA 88: Fábrica → Área → Linha → Equipamento</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={fetchHierarchy}
            variant="outline"
            className="bg-transparent border-neutral-700 text-neutral-300 hover:bg-neutral-800"
          >
            <RefreshCw className="mr-2 h-4 w-4" /> Atualizar
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        {/* Árvore Hierárquica */}
        <div className="lg:col-span-2">
          <HierarchyTree
            factories={factories}
            onSelectEquipment={handleSelectEquipment}
            onSelectLine={handleSelectLine}
            onSelectArea={handleSelectArea}
            onSelectFactory={handleSelectFactory}
          />
        </div>

        {/* Painel de Detalhes */}
        <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-neutral-200 mb-4">Detalhes</h3>

          {!selectedItem ? (
            <div className="text-center text-neutral-600 py-8">
              <p>Selecione um item na hierarquia para ver os detalhes</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="pb-4 border-b border-neutral-800">
                <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Tipo</p>
                <p className="text-sm font-semibold text-neutral-200 capitalize">{selectedType}</p>
              </div>

              <div className="pb-4 border-b border-neutral-800">
                <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Nome</p>
                <p className="text-sm font-semibold text-neutral-200">{selectedItem.nome}</p>
              </div>

              <div className="pb-4 border-b border-neutral-800">
                <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Código</p>
                <p className="text-sm font-mono text-emerald-400">{selectedItem.codigo}</p>
              </div>

              {selectedType === 'equipment' && (
                <>
                  <div className="pb-4 border-b border-neutral-800">
                    <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Tipo de Equipamento</p>
                    <p className="text-sm text-neutral-300">{selectedItem.tipo}</p>
                  </div>
                  <div className="pb-4 border-b border-neutral-800">
                    <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Estado Atual</p>
                    <p className="text-sm text-emerald-400 font-mono">{selectedItem.estado || 'N/A'}</p>
                  </div>
                </>
              )}

              {selectedType === 'line' && (
                <div className="pb-4 border-b border-neutral-800">
                  <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Equipamentos</p>
                  <p className="text-sm text-neutral-300">{selectedItem.equipamentos?.length || 0} equipamento(s)</p>
                </div>
              )}

              {selectedType === 'area' && (
                <div className="pb-4 border-b border-neutral-800">
                  <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Linhas</p>
                  <p className="text-sm text-neutral-300">{selectedItem.linhas?.length || 0} linha(s)</p>
                </div>
              )}

              {selectedType === 'factory' && (
                <div className="pb-4 border-b border-neutral-800">
                  <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Áreas</p>
                  <p className="text-sm text-neutral-300">{selectedItem.areas?.length || 0} área(s)</p>
                </div>
              )}

              <div className="pt-4">
                <Button
                  onClick={() => {
                    if (selectedType === 'equipment') {
                      navigate(`/admin/equipamentos`);
                    } else if (selectedType === 'line') {
                      navigate(`/linha/${selectedItem.id}`);
                    }
                  }}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  Ver Detalhes Completos
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FactoryHierarchy;
