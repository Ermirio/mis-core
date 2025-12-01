import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { TimeWindowGranularity } from '@/utils/timeWindows';
import { Loader2, Clock, TrendingUp, AlertTriangle } from 'lucide-react';

interface StrategicInitiative {
  id?: number;
  titulo: string;
  descricao: string;
  status: 'NAO_INICIADO' | 'EM_ANDAMENTO' | 'CONCLUIDO' | 'CANCELADO';
  responsavel: string;
  data_inicio: string | null;
  data_fim: string | null;
}

interface ProductionKPIs {
  planned_tons: number;
  actual_tons: number;
  actual_tph: number;
  min_required_tph: number | null;
  status_flag: 'NORMAL' | 'SUPERADO' | 'ATRASADO';
  window: {
    from: string;
    to: string;
    elapsedHours: number;
    hoursRemaining: number;
    granularity: string;
    tz: string;
  };
  notes: string[];
}

const FactoryManagement: React.FC = () => {
  // Strategic Initiatives State
  const [initiatives, setInitiatives] = useState<StrategicInitiative[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [currentInitiative, setCurrentInitiative] = useState<Partial<StrategicInitiative> | null>(null);

  // Production KPIs State
  const [period, setPeriod] = useState<TimeWindowGranularity>('shift');
  const [kpis, setKpis] = useState<ProductionKPIs | null>(null);
  const [loadingKpis, setLoadingKpis] = useState(false);

  const API_URL = import.meta.env.VITE_DJANGO_API_URL || 'http://localhost:8000/api';

  const fetchInitiatives = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/iniciativas-estrategicas/`);
      if (response.ok) {
        const data = await response.json();
        setInitiatives(data.results || data);
      }
    } catch (error) {
      console.error('Erro ao buscar iniciativas:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchKpis = async () => {
    setLoadingKpis(true);
    try {
      const response = await fetch(`${API_URL}/production/window/throughput/?granularity=${period}`);
      if (response.ok) {
        const data = await response.json();
        setKpis(data);
      } else {
        console.error('Erro ao buscar KPIs:', response.statusText);
      }
    } catch (error) {
      console.error('Erro ao buscar KPIs:', error);
    } finally {
      setLoadingKpis(false);
    }
  };

  useEffect(() => {
    fetchInitiatives();
  }, []);

  useEffect(() => {
    fetchKpis();
    const interval = setInterval(fetchKpis, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [period]);

  const handleSave = async () => {
    if (!currentInitiative) return;

    const method = currentInitiative.id ? 'PUT' : 'POST';
    const url = currentInitiative.id
      ? `${API_URL}/iniciativas-estrategicas/${currentInitiative.id}/`
      : `${API_URL}/iniciativas-estrategicas/`;

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentInitiative),
      });

      if (response.ok) {
        setIsDialogOpen(false);
        fetchInitiatives();
      }
    } catch (error) {
      console.error('Erro ao salvar iniciativa:', error);
    }
  };

  const openDialog = (initiative: Partial<StrategicInitiative> | null = null) => {
    setCurrentInitiative(initiative || { titulo: '', descricao: '', status: 'NAO_INICIADO', responsavel: '', data_inicio: null, data_fim: null });
    setIsDialogOpen(true);
  };

  return (
    <div className="p-6 space-y-8">
      {/* Header & KPIs */}
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Gestão da Fábrica</h1>
            <p className="text-gray-500">Monitoramento de produção e iniciativas estratégicas</p>
          </div>

          <div className="flex items-center gap-4">
            <Tabs value={period} onValueChange={(v) => setPeriod(v as TimeWindowGranularity)} className="w-[400px]">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="shift">Turno</TabsTrigger>
                <TabsTrigger value="day">Dia</TabsTrigger>
                <TabsTrigger value="week">Semana</TabsTrigger>
                <TabsTrigger value="month">Mês</TabsTrigger>
              </TabsList>
            </Tabs>
            <Button onClick={fetchKpis} variant="outline" size="icon" title="Atualizar KPIs">
              <Loader2 className={`h-4 w-4 ${loadingKpis ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Planejado */}
          <Card className="border-l-4 border-l-gray-500 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
                Tons Planejados
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">
                {kpis ? `${kpis.planned_tons.toLocaleString('pt-BR', { minimumFractionDigits: 2 })} t` : '--'}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Meta do Calendário
              </p>
            </CardContent>
          </Card>

          {/* Produção Real */}
          <Card className="border-l-4 border-l-blue-500 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
                Produção Real
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">
                {kpis ? `${kpis.actual_tons.toLocaleString('pt-BR', { minimumFractionDigits: 2 })} t` : '--'}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Total produzido no período
              </p>
            </CardContent>
          </Card>

          {/* Vazão Total (Actual TPH) */}
          <Card className="border-l-4 border-l-cyan-500 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
                Vazão Total
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <div className="text-3xl font-bold text-gray-900">
                  {kpis ? `${kpis.actual_tph.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '--'}
                </div>
                <span className="text-sm font-medium text-gray-500">t/h</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Média do período
              </p>
            </CardContent>
          </Card>

          {/* Vazão Necessária */}
          <Card className={`border-l-4 shadow-sm ${kpis?.status_flag === 'ATRASADO' ? 'border-l-red-500 bg-red-50' : 'border-l-indigo-500'}`}>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-medium text-gray-500 uppercase tracking-wider">
                  Vazão Necessária
                </CardTitle>
                {kpis?.status_flag === 'SUPERADO' && <Badge className="bg-green-500 hover:bg-green-600">Plano Superado</Badge>}
                {kpis?.status_flag === 'ATRASADO' && <Badge variant="destructive">Prazo Encerrado</Badge>}
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <div className="text-3xl font-bold text-gray-900">
                  {kpis ? (
                    kpis.min_required_tph === null ? '--' :
                      `${kpis.min_required_tph.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                  ) : '--'}
                </div>
                <span className="text-sm font-medium text-gray-500">t/h</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                <Clock className="h-3 w-3" />
                {kpis ? `${kpis.window.hoursRemaining}h restantes` : '--'}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="border-t border-gray-200 my-8"></div>

      {/* Strategic Initiatives Section */}
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900">Iniciativas Estratégicas</h2>
          <Button onClick={() => openDialog()}>Nova Iniciativa</Button>
        </div>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{currentInitiative?.id ? 'Editar' : 'Nova'} Iniciativa Estratégica</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <Input
                placeholder="Título"
                value={currentInitiative?.titulo || ''}
                onChange={(e) => setCurrentInitiative({ ...currentInitiative, titulo: e.target.value })}
              />
              <Textarea
                placeholder="Descrição"
                value={currentInitiative?.descricao || ''}
                onChange={(e) => setCurrentInitiative({ ...currentInitiative, descricao: e.target.value })}
              />
              <Input
                placeholder="Responsável"
                value={currentInitiative?.responsavel || ''}
                onChange={(e) => setCurrentInitiative({ ...currentInitiative, responsavel: e.target.value })}
              />
              <Select
                value={currentInitiative?.status || 'NAO_INICIADO'}
                onValueChange={(value) => setCurrentInitiative({ ...currentInitiative, status: value as StrategicInitiative['status'] })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="NAO_INICIADO">Não Iniciado</SelectItem>
                  <SelectItem value="EM_ANDAMENTO">Em Andamento</SelectItem>
                  <SelectItem value="CONCLUIDO">Concluído</SelectItem>
                  <SelectItem value="CANCELADO">Cancelado</SelectItem>
                </SelectContent>
              </Select>
              <div className="flex gap-4">
                <Input
                  type="date"
                  value={currentInitiative?.data_inicio || ''}
                  onChange={(e) => setCurrentInitiative({ ...currentInitiative, data_inicio: e.target.value })}
                />
                <Input
                  type="date"
                  value={currentInitiative?.data_fim || ''}
                  onChange={(e) => setCurrentInitiative({ ...currentInitiative, data_fim: e.target.value })}
                />
              </div>
              <Button onClick={handleSave} className="w-full">Salvar</Button>
            </div>
          </DialogContent>
        </Dialog>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Título</TableHead>
                <TableHead>Responsável</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Início</TableHead>
                <TableHead>Fim</TableHead>
                <TableHead>Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {initiatives.map((initiative) => (
                <TableRow key={initiative.id}>
                  <TableCell className="font-medium">{initiative.titulo}</TableCell>
                  <TableCell>{initiative.responsavel}</TableCell>
                  <TableCell>
                    <Badge variant={
                      initiative.status === 'CONCLUIDO' ? 'default' :
                        initiative.status === 'EM_ANDAMENTO' ? 'secondary' :
                          initiative.status === 'CANCELADO' ? 'destructive' : 'outline'
                    }>
                      {initiative.status.replace(/_/g, ' ')}
                    </Badge>
                  </TableCell>
                  <TableCell>{initiative.data_inicio}</TableCell>
                  <TableCell>{initiative.data_fim}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" onClick={() => openDialog(initiative)}>
                      Editar
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {initiatives.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-gray-500">
                    Nenhuma iniciativa cadastrada.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
};

export default FactoryManagement;
