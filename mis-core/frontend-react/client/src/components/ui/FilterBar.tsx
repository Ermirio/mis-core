import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Calendar, Filter, Download } from 'lucide-react';

interface FilterBarProps {
    // Período
    periodoTipo: 'rapido' | 'personalizado';
    setPeriodoTipo: (tipo: 'rapido' | 'personalizado') => void;
    periodoRapido: string;
    setPeriodoRapido: (periodo: string) => void;
    dataInicio?: string;
    setDataInicio?: (data: string) => void;
    dataFim?: string;
    setDataFim?: (data: string) => void;

    // Granularidade
    granularidade: 'hora' | 'turno' | 'dia' | 'semana';
    setGranularidade: (gran: 'hora' | 'turno' | 'dia' | 'semana') => void;

    // Turno (opcional)
    turno?: string;
    setTurno?: (turno: string) => void;
    turnos?: Array<{ id: number; nome: string; codigo: string }>;

    // Callbacks
    onAplicar?: () => void;
    onLimpar?: () => void;
    onExportar?: () => void;
}

const FilterBar: React.FC<FilterBarProps> = ({
    periodoTipo,
    setPeriodoTipo,
    periodoRapido,
    setPeriodoRapido,
    dataInicio,
    setDataInicio,
    dataFim,
    setDataFim,
    granularidade,
    setGranularidade,
    turno,
    setTurno,
    turnos = [],
    onAplicar,
    onLimpar,
    onExportar,
}) => {
    const hoje = new Date().toISOString().split('T')[0];

    return (
        <Card className="mb-6">
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <Filter className="w-5 h-5" />
                    Filtros de Análise
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Tipo de Período */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Tipo de Período
                        </label>
                        <Select value={periodoTipo} onValueChange={(v) => setPeriodoTipo(v as 'rapido' | 'personalizado')}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="rapido">Período Rápido</SelectItem>
                                <SelectItem value="personalizado">Personalizado</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Período Rápido */}
                    {periodoTipo === 'rapido' && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Período
                            </label>
                            <Select value={periodoRapido} onValueChange={setPeriodoRapido}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="ultima_hora">Última Hora</SelectItem>
                                    <SelectItem value="turno_atual">Turno Atual</SelectItem>
                                    <SelectItem value="turno_anterior">Turno Anterior</SelectItem>
                                    <SelectItem value="hoje">Hoje</SelectItem>
                                    <SelectItem value="ontem">Ontem</SelectItem>
                                    <SelectItem value="ultimos_7_dias">Últimos 7 Dias</SelectItem>
                                    <SelectItem value="ultimos_30_dias">Últimos 30 Dias</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    )}

                    {/* Período Personalizado */}
                    {periodoTipo === 'personalizado' && (
                        <>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Data Início
                                </label>
                                <input
                                    type="date"
                                    value={dataInicio}
                                    onChange={(e) => setDataInicio?.(e.target.value)}
                                    max={hoje}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Data Fim
                                </label>
                                <input
                                    type="date"
                                    value={dataFim}
                                    onChange={(e) => setDataFim?.(e.target.value)}
                                    max={hoje}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                            </div>
                        </>
                    )}

                    {/* Granularidade */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Granularidade
                        </label>
                        <Select value={granularidade} onValueChange={(v) => setGranularidade(v as any)}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="hora">Por Hora</SelectItem>
                                <SelectItem value="turno">Por Turno</SelectItem>
                                <SelectItem value="dia">Por Dia</SelectItem>
                                <SelectItem value="semana">Por Semana</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Turno (se granularidade for turno) */}
                    {granularidade === 'turno' && setTurno && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Turno
                            </label>
                            <Select value={turno} onValueChange={setTurno}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="todos">Todos os Turnos</SelectItem>
                                    {turnos.map(t => (
                                        <SelectItem key={t.id} value={t.codigo}>
                                            {t.nome}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    )}
                </div>

                {/* Botões de Ação */}
                <div className="flex gap-2 mt-4">
                    <Button onClick={onAplicar} size="sm">
                        <Filter className="w-4 h-4 mr-2" />
                        Aplicar Filtros
                    </Button>
                    <Button onClick={onLimpar} variant="outline" size="sm">
                        Limpar
                    </Button>
                    {onExportar && (
                        <Button onClick={onExportar} variant="outline" size="sm" className="ml-auto">
                            <Download className="w-4 h-4 mr-2" />
                            Exportar Dados
                        </Button>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default FilterBar;