import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { AlertCircle, CheckCircle, Clock, TrendingUp, Factory, Calendar } from 'lucide-react';

// Cores para o gráfico
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#ff7300'];

interface LossData {
    categoria: string;
    toneladas: number;
}

interface StrategicLossResponse {
    total_toneladas: number;
    breakdown: LossData[];
}

interface EventoParada {
    id: number;
    maquina: string;
    categoria_clp: string;
    categoria_display: string;
    inicio: string;
    fim: string | null;
    duracao_segundos: number;
    toneladas_perdidas: number;
    detalhe_operador: string | null;
    justificado: boolean;
}

interface MonthlyStats {
    mes: string;
    total_toneladas: number;
    media_oee: number;
}

interface OpHistory {
    id: number;
    ordem_producao: string;
    produto: string;
    data_inicio: string;
    data_fim: string | null;
    total_produzido: number;
    total_planejado: number;
    status: string;
}

interface StrategicAnalysisProps {
    linhaId: number;
}

export function StrategicAnalysis({ linhaId }: StrategicAnalysisProps) {
    const [lossData, setLossData] = useState<StrategicLossResponse | null>(null);
    const [eventos, setEventos] = useState<EventoParada[]>([]);
    const [monthlyStats, setMonthlyStats] = useState<MonthlyStats | null>(null);
    const [opHistory, setOpHistory] = useState<OpHistory[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedEvento, setSelectedEvento] = useState<EventoParada | null>(null);
    const [justificativa, setJustificativa] = useState('');
    const [dialogOpen, setDialogOpen] = useState(false);

    // Filtros
    const [selectedMonth, setSelectedMonth] = useState<string>(String(new Date().getMonth() + 1));
    const [selectedYear, setSelectedYear] = useState<string>(String(new Date().getFullYear()));
    const [selectedDay, setSelectedDay] = useState<string>('');
    const [selectedTurno, setSelectedTurno] = useState<string>('');

    const API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://localhost:8000/api';

    const fetchData = async () => {
        try {
            // 1. Fetch Loss Data (InfluxDB)
            const lossRes = await fetch(`${API_URL}/linhas/${linhaId}/strategic-loss/?horas=12`);
            const lossJson = await lossRes.json();
            setLossData(lossJson);

            // 2. Fetch Eventos (MySQL)
            const eventosRes = await fetch(`${API_URL}/eventos-parada/?ordering=-inicio`);
            const eventosJson = await eventosRes.json();
            if (eventosJson.results && Array.isArray(eventosJson.results)) {
                setEventos(eventosJson.results);
            } else if (Array.isArray(eventosJson)) {
                setEventos(eventosJson);
            } else {
                setEventos([]);
            }

            // 3. Fetch Monthly Stats
            const statsRes = await fetch(`${API_URL}/linhas/${linhaId}/monthly-production-stats/`);
            if (statsRes.ok) {
                setMonthlyStats(await statsRes.json());
            }

            // 4. Fetch OP History with Filters
            let opUrl = `${API_URL}/linhas/${linhaId}/monthly-op-history/?mes=${selectedMonth}&ano=${selectedYear}`;
            if (selectedDay) {
                opUrl += `&dia=${selectedDay}`;
            }
            if (selectedTurno) {
                opUrl += `&turno=${selectedTurno}`;
            }
            const opsRes = await fetch(opUrl);
            if (opsRes.ok) {
                setOpHistory(await opsRes.json());
            }

        } catch (error) {
            console.error("Erro ao buscar dados estratégicos:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 10000); // Atualiza a cada 10s
        return () => clearInterval(interval);
    }, [linhaId, selectedMonth, selectedYear, selectedDay, selectedTurno]);

    const handleJustificar = async () => {
        if (!selectedEvento) return;

        try {
            await fetch(`${API_URL}/eventos-parada/${selectedEvento.id}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    detalhe_operador: justificativa,
                    justificado: true
                }),
            });
            setDialogOpen(false);
            fetchData(); // Recarrega dados
        } catch (error) {
            console.error("Erro ao justificar evento:", error);
        }
    };

    const openJustificativa = (evento: EventoParada) => {
        setSelectedEvento(evento);
        setJustificativa(evento.detalhe_operador || '');
        setDialogOpen(true);
    };

    if (loading) return <div>Carregando análise estratégica...</div>;

    return (
        <div className="space-y-6 p-4">
            {/* Seção 1: Visão Geral do Mês */}
            {monthlyStats && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Mês de Referência</CardTitle>
                            <Calendar className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{monthlyStats.mes}</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Produção Total</CardTitle>
                            <Factory className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{monthlyStats.total_toneladas} ton</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">OEE Médio</CardTitle>
                            <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{monthlyStats.media_oee}%</div>
                        </CardContent>
                    </Card>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Coluna 1: Visão Gerencial (Gráfico de Perdas) */}
                <Card className="h-full">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <AlertCircle className="h-5 w-5 text-red-500" />
                            Perdas por Categoria (Últimas 12h)
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[300px] w-full">
                            {lossData && lossData.breakdown.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={lossData.breakdown}
                                            cx="50%"
                                            cy="50%"
                                            labelLine={false}
                                            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                            outerRadius={100}
                                            fill="#8884d8"
                                            dataKey="toneladas"
                                            nameKey="categoria"
                                        >
                                            {lossData.breakdown.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip formatter={(value: number) => [`${value.toFixed(3)} ton`, 'Perda']} />
                                        <Legend />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="flex items-center justify-center h-full text-gray-500">
                                    Sem dados de perda registrados
                                </div>
                            )}
                        </div>
                        <div className="mt-4 text-center">
                            <p className="text-lg font-bold text-red-600">
                                Total Perdido: {lossData?.total_toneladas.toFixed(3)} ton
                            </p>
                        </div>
                    </CardContent>
                </Card>

                {/* Coluna 2: Visão Operador (Lista de Eventos) */}
                <Card className="h-full flex flex-col">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Clock className="h-5 w-5 text-blue-500" />
                            Últimos Eventos de Parada
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-auto max-h-[400px]">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Hora</TableHead>
                                    <TableHead>Máquina</TableHead>
                                    <TableHead>Motivo (CLP)</TableHead>
                                    <TableHead>Duração</TableHead>
                                    <TableHead>Ação</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {eventos.map((evento) => (
                                    <TableRow key={evento.id} className={evento.justificado ? 'bg-green-50/50' : ''}>
                                        <TableCell>{new Date(evento.inicio).toLocaleTimeString()}</TableCell>
                                        <TableCell>{evento.maquina}</TableCell>
                                        <TableCell>
                                            <span className="font-medium">{evento.categoria_display || evento.categoria_clp}</span>
                                            {evento.detalhe_operador && (
                                                <p className="text-xs text-gray-500 mt-1">Obs: {evento.detalhe_operador}</p>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            {evento.fim ?
                                                `${(evento.duracao_segundos / 60).toFixed(1)} min` :
                                                <span className="text-red-500 animate-pulse">Em andamento</span>
                                            }
                                        </TableCell>
                                        <TableCell>
                                            <Button
                                                variant={evento.justificado ? "outline" : "default"}
                                                size="sm"
                                                onClick={() => openJustificativa(evento)}
                                            >
                                                {evento.justificado ? <CheckCircle className="h-4 w-4" /> : "Justificar"}
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            </div>

            {/* Seção 3: Histórico de OPs */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <Factory className="h-5 w-5 text-green-600" />
                        Histórico de Ordens de Produção
                    </CardTitle>
                    <div className="flex gap-2">
                        <select
                            className="border rounded p-1"
                            value={selectedMonth}
                            onChange={(e) => setSelectedMonth(e.target.value)}
                        >
                            {Array.from({ length: 12 }, (_, i) => (
                                <option key={i + 1} value={i + 1}>
                                    {new Date(0, i).toLocaleString('default', { month: 'long' })}
                                </option>
                            ))}
                        </select>
                        <select
                            className="border rounded p-1"
                            value={selectedYear}
                            onChange={(e) => setSelectedYear(e.target.value)}
                        >
                            <option value="2024">2024</option>
                            <option value="2025">2025</option>
                        </select>
                        <input
                            type="number"
                            placeholder="Dia"
                            className="border rounded p-1 w-16"
                            min="1" max="31"
                            value={selectedDay}
                            onChange={(e) => setSelectedDay(e.target.value)}
                        />
                        <select
                            className="border rounded p-1"
                            value={selectedTurno}
                            onChange={(e) => setSelectedTurno(e.target.value)}
                        >
                            <option value="">Todos Turnos</option>
                            <option value="A">Turno A</option>
                            <option value="B">Turno B</option>
                            <option value="C">Turno C</option>
                        </select>
                    </div>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>OP</TableHead>
                                <TableHead>Produto</TableHead>
                                <TableHead>Início</TableHead>
                                <TableHead>Fim</TableHead>
                                <TableHead>Planejado</TableHead>
                                <TableHead>Produzido</TableHead>
                                <TableHead>Status</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {opHistory.length > 0 ? (
                                opHistory.map((op) => (
                                    <TableRow key={op.id}>
                                        <TableCell className="font-medium">{op.ordem_producao}</TableCell>
                                        <TableCell>{op.produto}</TableCell>
                                        <TableCell>{new Date(op.data_inicio).toLocaleString()}</TableCell>
                                        <TableCell>{op.data_fim ? new Date(op.data_fim).toLocaleString() : '-'}</TableCell>
                                        <TableCell>{op.total_planejado > 0 ? `${op.total_planejado} ton` : '-'}</TableCell>
                                        <TableCell>{op.total_produzido} ton</TableCell>
                                        <TableCell>
                                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${op.status.includes('Concluída') ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                                                }`}>
                                                {op.status}
                                            </span>
                                        </TableCell>
                                    </TableRow>
                                ))
                            ) : (
                                <TableRow>
                                    <TableCell colSpan={7} className="text-center text-gray-500">
                                        Nenhuma Ordem de Produção encontrada neste período.
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {/* Dialog de Justificativa */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Justificar Parada</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label>Detalhe do Operador</Label>
                            <Textarea
                                placeholder="Descreva o motivo real da parada..."
                                value={justificativa}
                                onChange={(e) => setJustificativa(e.target.value)}
                            />
                        </div>
                    </div>
                    <div className="flex justify-end">
                        <Button onClick={handleJustificar}>Salvar Justificativa</Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
