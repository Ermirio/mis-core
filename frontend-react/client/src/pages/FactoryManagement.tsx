import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface StrategicInitiative {
  id?: number;
  titulo: string;
  descricao: string;
  status: 'NAO_INICIADO' | 'EM_ANDAMENTO' | 'CONCLUIDO' | 'CANCELADO';
  responsavel: string;
  data_inicio: string | null;
  data_fim: string | null;
}

const FactoryManagement: React.FC = () => {
  const [initiatives, setInitiatives] = useState<StrategicInitiative[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [currentInitiative, setCurrentInitiative] = useState<Partial<StrategicInitiative> | null>(null);

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

  useEffect(() => {
    fetchInitiatives();
  }, []);

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
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Gestão da Fábrica</h1>
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
              <TableCell>{initiative.titulo}</TableCell>
              <TableCell>{initiative.responsavel}</TableCell>
              <TableCell>{initiative.status.replace(/_/g, ' ')}</TableCell>
              <TableCell>{initiative.data_inicio}</TableCell>
              <TableCell>{initiative.data_fim}</TableCell>
              <TableCell>
                <Button variant="outline" size="sm" onClick={() => openDialog(initiative)}>
                  Editar
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

export default FactoryManagement;
