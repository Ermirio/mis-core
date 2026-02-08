import React, { useState } from "react";
import { ChevronRight, ChevronDown, Factory, MapPin, Layers, Cpu } from "lucide-react";
import EquipmentStateIndicator, { EquipmentState } from "./EquipmentStateIndicator";

interface Equipment {
  id: number;
  nome: string;
  codigo: string;
  tipo: string;
  estado?: EquipmentState;
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

interface HierarchyTreeProps {
  factories: Factory[];
  onSelectEquipment?: (equipment: Equipment) => void;
  onSelectLine?: (line: Line) => void;
  onSelectArea?: (area: Area) => void;
  onSelectFactory?: (factory: Factory) => void;
}

const HierarchyTree: React.FC<HierarchyTreeProps> = ({
  factories,
  onSelectEquipment,
  onSelectLine,
  onSelectArea,
  onSelectFactory
}) => {
  const [expandedFactories, setExpandedFactories] = useState<Set<number>>(new Set());
  const [expandedAreas, setExpandedAreas] = useState<Set<number>>(new Set());
  const [expandedLines, setExpandedLines] = useState<Set<number>>(new Set());

  const toggleFactory = (id: number) => {
    const newSet = new Set(expandedFactories);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setExpandedFactories(newSet);
  };

  const toggleArea = (id: number) => {
    const newSet = new Set(expandedAreas);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setExpandedAreas(newSet);
  };

  const toggleLine = (id: number) => {
    const newSet = new Set(expandedLines);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setExpandedLines(newSet);
  };

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-4">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-neutral-200 flex items-center gap-2">
          <Layers className="w-5 h-5 text-emerald-500" />
          Hierarquia ISA 88
        </h3>
        <p className="text-xs text-neutral-500 mt-1">
          Fábrica → Área → Linha → Equipamento
        </p>
      </div>

      <div className="space-y-2">
        {factories.map((factory) => (
          <div key={factory.id} className="border border-neutral-800 rounded-lg overflow-hidden">
            {/* Factory Level */}
            <div
              className="flex items-center gap-2 p-3 bg-neutral-900 hover:bg-neutral-800 cursor-pointer transition-colors"
              onClick={() => {
                toggleFactory(factory.id);
                onSelectFactory?.(factory);
              }}
            >
              <button className="flex-shrink-0">
                {expandedFactories.has(factory.id) ? (
                  <ChevronDown className="w-4 h-4 text-neutral-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-neutral-400" />
                )}
              </button>
              <Factory className="w-5 h-5 text-blue-400" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-neutral-200">{factory.nome}</p>
                <p className="text-xs text-neutral-500 font-mono">{factory.codigo}</p>
              </div>
              <span className="text-xs text-neutral-600">
                {factory.areas.length} área(s)
              </span>
            </div>

            {/* Areas */}
            {expandedFactories.has(factory.id) && (
              <div className="pl-6 bg-neutral-950/50">
                {factory.areas.map((area) => (
                  <div key={area.id} className="border-l-2 border-neutral-800">
                    <div
                      className="flex items-center gap-2 p-2 hover:bg-neutral-900 cursor-pointer transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleArea(area.id);
                        onSelectArea?.(area);
                      }}
                    >
                      <button className="flex-shrink-0">
                        {expandedAreas.has(area.id) ? (
                          <ChevronDown className="w-4 h-4 text-neutral-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-neutral-400" />
                        )}
                      </button>
                      <MapPin className="w-4 h-4 text-purple-400" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-neutral-300">{area.nome}</p>
                        <p className="text-xs text-neutral-600 font-mono">{area.codigo}</p>
                      </div>
                      <span className="text-xs text-neutral-600">
                        {area.linhas.length} linha(s)
                      </span>
                    </div>

                    {/* Lines */}
                    {expandedAreas.has(area.id) && (
                      <div className="pl-6">
                        {area.linhas.map((line) => (
                          <div key={line.id} className="border-l-2 border-neutral-800">
                            <div
                              className="flex items-center gap-2 p-2 hover:bg-neutral-900 cursor-pointer transition-colors"
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleLine(line.id);
                                onSelectLine?.(line);
                              }}
                            >
                              <button className="flex-shrink-0">
                                {expandedLines.has(line.id) ? (
                                  <ChevronDown className="w-4 h-4 text-neutral-400" />
                                ) : (
                                  <ChevronRight className="w-4 h-4 text-neutral-400" />
                                )}
                              </button>
                              <Layers className="w-4 h-4 text-emerald-400" />
                              <div className="flex-1">
                                <p className="text-sm font-medium text-neutral-300">{line.nome}</p>
                                <p className="text-xs text-neutral-600 font-mono">{line.codigo}</p>
                              </div>
                              <span className="text-xs text-neutral-600">
                                {line.equipamentos.length} equip.
                              </span>
                            </div>

                            {/* Equipment */}
                            {expandedLines.has(line.id) && (
                              <div className="pl-6">
                                {line.equipamentos.map((equipment) => (
                                  <div
                                    key={equipment.id}
                                    className="flex items-center gap-2 p-2 hover:bg-neutral-900 cursor-pointer transition-colors border-l-2 border-neutral-800"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onSelectEquipment?.(equipment);
                                    }}
                                  >
                                    <div className="w-4 flex-shrink-0"></div>
                                    <Cpu className="w-4 h-4 text-amber-400" />
                                    <div className="flex-1">
                                      <p className="text-sm text-neutral-300">{equipment.nome}</p>
                                      <p className="text-xs text-neutral-600 font-mono">{equipment.codigo}</p>
                                    </div>
                                    {equipment.estado && (
                                      <EquipmentStateIndicator
                                        state={equipment.estado}
                                        size="sm"
                                        showLabel={false}
                                        showIcon={true}
                                      />
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default HierarchyTree;
