import React, { useState } from "react";
import { Plus, Edit, Trash2, Activity, RefreshCw } from "lucide-react";
import { Button } from "../ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "../ui/dialog";
import { toast } from "sonner";
import SensorForm from "./SensorForm";
import { DJANGO_API_URL } from "@/config/api";

interface SensorInlineManagerProps {
    equipmentId: number;
    sensors: any[];
    onUpdate: () => void;
}

const SensorInlineManager: React.FC<SensorInlineManagerProps> = ({ equipmentId, sensors, onUpdate }) => {

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [selectedSensor, setSelectedSensor] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Initial data for the form
    const getInitialData = () => {
        if (selectedSensor) return selectedSensor;
        return {
            equipamento: equipmentId,
            ativo: true,
            tipo: "INPUT_FLOAT"
        };
    };

    // Helper to get cookie
    const getCookie = (name: string) => {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    const handleCreateOrUpdate = async (values: any) => {
        setIsSubmitting(true);
        try {
            // Force equipment ID
            const payload = { ...values, equipamento: equipmentId };

            const url = selectedSensor
                ? `${DJANGO_API_URL}/sensores/${selectedSensor.id}/`
                : `${DJANGO_API_URL}/sensores/`;

            const method = selectedSensor ? 'PUT' : 'POST';
            const csrftoken = getCookie('csrftoken');

            const resp = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken || '',
                },
                body: JSON.stringify(payload),
            });

            if (!resp.ok) {
                const errData = await resp.json();
                throw new Error(JSON.stringify(errData));
            }

            toast.success(selectedSensor ? "Sensor atualizado!" : "Sensor adicionado!");
            setIsDialogOpen(false);
            onUpdate();

        } catch (error: any) {
            console.error("Erro ao salvar sensor", error);
            let msg = "Erro ao salvar.";
            try {
                const errObj = JSON.parse(error.message);
                if (errObj.detail) msg = errObj.detail;
                else if (typeof errObj === 'object') msg = Object.values(errObj).flat().join(', ');
            } catch (e) { /* ignore */ }
            toast.error(msg);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async (sensor: any) => {
        if (!confirm(`Tem certeza que deseja remover o sensor "${sensor.nome}"?`)) return;

        try {
            const csrftoken = getCookie('csrftoken');
            const resp = await fetch(`${DJANGO_API_URL}/sensores/${sensor.id}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': csrftoken || '',
                },
            });

            if (!resp.ok) throw new Error("Falha ao deletar");

            toast.success("Sensor removido!");
            onUpdate();
        } catch (error) {
            console.error("Erro ao deletar sensor", error);
            toast.error("Erro ao remover sensor.");
        }
    };

    return (
        <div className="space-y-4 border border-neutral-800 rounded-md p-4 bg-neutral-900/20">
            <div className="flex items-center justify-between">
                <h3 className="text-md font-medium text-neutral-200 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-blue-500" />
                    Sensores de Processo ({sensors.length})
                </h3>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={onUpdate} className="h-8 bg-transparent border-neutral-700 hover:bg-neutral-800 text-neutral-400">
                        <RefreshCw className="w-3 h-3" />
                    </Button>
                    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                        <DialogTrigger asChild>
                            <Button
                                size="sm"
                                onClick={() => setSelectedSensor(null)}
                                className="h-8 bg-blue-600 hover:bg-blue-700 text-white"
                            >
                                <Plus className="mr-1 h-3 w-3" /> Adicionar Sensor
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-neutral-950 border-neutral-800 text-neutral-200 sm:max-w-md">
                            <DialogHeader>
                                <DialogTitle className="text-neutral-100">
                                    {selectedSensor ? "Editar Sensor" : "Novo Sensor"}
                                </DialogTitle>
                                <DialogDescription className="text-neutral-500">
                                    Configure as variáveis de processo monitoradas.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="mt-4">
                                <SensorForm
                                    initialData={getInitialData()}
                                    onSubmit={handleCreateOrUpdate}
                                    onCancel={() => setIsDialogOpen(false)}
                                    isLoading={isSubmitting}
                                />
                            </div>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {sensors.length === 0 ? (
                <div className="text-center py-8 text-neutral-500 text-sm border-2 border-dashed border-neutral-800 rounded-lg">
                    Nenhum sensor configurado para este equipamento.
                </div>
            ) : (
                <div className="rounded-md border border-neutral-800 overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-neutral-900 text-neutral-400 font-medium">
                            <tr>
                                <th className="px-4 py-2">Código</th>
                                <th className="px-4 py-2">Nome</th>
                                <th className="px-4 py-2">Tipo</th>
                                <th className="px-4 py-2">Tag BD</th>
                                <th className="px-4 py-2 text-right">Ações</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-800">
                            {sensors.map((sensor) => (
                                <tr key={sensor.id} className="hover:bg-neutral-800/50 group">
                                    <td className="px-4 py-2 font-mono text-xs text-neutral-300">{sensor.codigo}</td>
                                    <td className="px-4 py-2 text-neutral-200">{sensor.nome}</td>
                                    <td className="px-4 py-2"><span className="text-[10px] bg-neutral-800 px-1 rounded border border-neutral-700">{sensor.tipo}</span></td>
                                    <td className="px-4 py-2 text-xs text-neutral-500 font-mono">{sensor.tag_influxdb}</td>
                                    <td className="px-4 py-2 text-right">
                                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 text-neutral-400 hover:text-white hover:bg-neutral-700"
                                                onClick={() => { setSelectedSensor(sensor); setIsDialogOpen(true); }}
                                            >
                                                <Edit className="h-3 w-3" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 text-neutral-400 hover:text-red-400 hover:bg-red-950/30"
                                                onClick={() => handleDelete(sensor)}
                                            >
                                                <Trash2 className="h-3 w-3" />
                                            </Button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default SensorInlineManager;
