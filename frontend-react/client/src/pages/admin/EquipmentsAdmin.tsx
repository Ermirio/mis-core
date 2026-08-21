import React, { useEffect, useState } from "react";
import { Plus, CheckCircle, XCircle, Settings, Edit, Trash2, TrendingUp, Activity } from "lucide-react";
import EquipmentStateIndicator from "../../components/admin/EquipmentStateIndicator";
import AdminDataGrid from "../../components/admin/AdminDataGrid";
import EquipmentForm from "../../components/admin/EquipmentForm";
import { Button } from "../../components/ui/button";
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from "../../components/ui/sheet";
import { toast } from "sonner";
import { DJANGO_API_URL } from '@/config/api';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "../../components/ui/dialog";

const EquipmentsAdmin: React.FC = () => {


    const [equipments, setEquipments] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [isSheetOpen, setIsSheetOpen] = useState(false);
    const [selectedEquipment, setSelectedEquipment] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [equipmentToDelete, setEquipmentToDelete] = useState<any | null>(null);

    const fetchEquipments = async () => {
        setLoading(true);
        try {
            const resp = await fetch(`${DJANGO_API_URL}/equipamentos/`);
            const data = await resp.json();
            setEquipments(data.results || data);
        } catch (error) {
            console.error("Erro ao carregar equipamentos", error);
            toast.error("Falha ao carregar lista de equipamentos.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchEquipments();
    }, []);

    const handleCreateOrUpdate = async (values: any) => {
        setIsSubmitting(true);
        try {
            const url = selectedEquipment
                ? `${DJANGO_API_URL}/equipamentos/${selectedEquipment.id}/`
                : `${DJANGO_API_URL}/equipamentos/`;

            const method = selectedEquipment ? 'PUT' : 'POST';

            const resp = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    // 'X-CSRFToken': ... (se necessario, mas API costuma ser Token Auth ou Session)
                },
                body: JSON.stringify(values),
            });

            if (!resp.ok) throw new Error("Falha ao salvar");

            toast.success(selectedEquipment ? "Equipamento atualizado!" : "Equipamento criado!");
            setIsSheetOpen(false);
            fetchEquipments();

        } catch (error) {
            console.error("Erro ao salvar equipamento", error);
            toast.error("Erro ao salvar. Verifique os dados.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async () => {
        if (!equipmentToDelete) return;

        try {
            const resp = await fetch(`${DJANGO_API_URL}/equipamentos/${equipmentToDelete.id}/`, {
                method: 'DELETE',
            });
            if (!resp.ok) throw new Error("Falha ao excluir");

            toast.success("Equipamento excluído.");
            setDeleteDialogOpen(false);
            setEquipmentToDelete(null);
            fetchEquipments();
        } catch (error) {
            console.error(error);
            toast.error("Erro ao excluir equipamento.");
        }
    };

    const handleRefresh = async () => {
        await fetchEquipments();
        if (selectedEquipment) {
            try {
                const resp = await fetch(`${DJANGO_API_URL}/equipamentos/${selectedEquipment.id}/`);
                if (resp.ok) {
                    const data = await resp.json();
                    setSelectedEquipment(data);
                }
            } catch (error) {
                console.error("Erro ao atualizar dados do equipamento selecionado", error);
            }
        }
    };

    const columns = [
        { key: "id", header: "ID", width: "50px" },
        {
            key: "nome",
            header: "Equipamento",
            render: (item: any) => (
                <div>
                    <p className="text-neutral-200 font-medium">{item.nome}</p>
                    <p className="text-xs text-neutral-600">{item.linha_nome || 'Sem linha'}</p>
                </div>
            )
        },
        {
            key: "codigo",
            header: "Tag / Código",
            render: (item: any) => <span className="text-emerald-400 font-mono">{item.codigo}</span>
        },
        {
            key: "tipo_display",
            header: "Tipo",
            render: (item: any) => (
                <span className="px-2 py-0.5 rounded text-xs bg-neutral-800 border border-neutral-700 text-neutral-300">
                    {item.tipo_display || item.tipo}
                </span>
            )
        },
        {
            key: "estado",
            header: "Estado",
            render: (item: any) => (
                <EquipmentStateIndicator
                    state={item.estado || 'RUN'}
                    size="sm"
                    showLabel={false}
                />
            )
        },
        {
            key: "velocidade_nominal",
            header: "Velocidade Nominal",
            render: (item: any) => (
                <div className="flex items-center gap-1">
                    <Activity className="w-3 h-3 text-neutral-500" />
                    <span className="text-neutral-300 font-mono text-sm">{item.velocidade_nominal} u/min</span>
                </div>
            )
        },
        {
            key: "meta_oee",
            header: "Meta OEE",
            render: (item: any) => (
                <div className="flex items-center gap-1">
                    <TrendingUp className="w-3 h-3 text-blue-500" />
                    <span className="text-blue-400 font-mono">{item.meta_oee}%</span>
                </div>
            )
        },
        {
            key: "actions",
            header: "Ações",
            width: "100px",
            render: (item: any) => (
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-neutral-400 hover:text-white hover:bg-neutral-800"
                        onClick={() => {
                            setSelectedEquipment(item);
                            setIsSheetOpen(true);
                        }}
                    >
                        <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-900 hover:text-red-500 hover:bg-red-950/30"
                        onClick={() => {
                            setEquipmentToDelete(item);
                            setDeleteDialogOpen(true);
                        }}
                    >
                        <Trash2 className="h-4 w-4" />
                    </Button>
                </div>
            )
        }
    ];

    return (
        <div className="h-full flex flex-col space-y-4">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-semibold text-neutral-100">Gerenciamento de Equipamentos</h2>
                    <p className="text-sm text-neutral-500">Configure os ativos monitorados pelo sistema.</p>
                </div>

                <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
                    <SheetTrigger asChild>
                        <Button
                            onClick={() => setSelectedEquipment(null)}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white"
                        >
                            <Plus className="mr-2 h-4 w-4" /> Novo Equipamento
                        </Button>
                    </SheetTrigger>
                    <SheetContent className="bg-neutral-950 border-l border-neutral-800 text-neutral-200 sm:max-w-xl w-full sm:w-[600px]">
                        <SheetHeader>
                            <SheetTitle className="text-neutral-100">
                                {selectedEquipment ? "Editar Equipamento" : "Novo Equipamento"}
                            </SheetTitle>
                            <SheetDescription className="text-neutral-500">
                                Preencha os dados técnicos do equipamento. O Tag/Código deve ser único.
                            </SheetDescription>
                        </SheetHeader>
                        <div className="mt-6 h-[calc(100vh-180px)]">
                            <EquipmentForm
                                initialData={selectedEquipment}
                                onSubmit={handleCreateOrUpdate}
                                onCancel={() => setIsSheetOpen(false)}
                                isLoading={isSubmitting}
                                onRefresh={handleRefresh}
                            />
                        </div>
                    </SheetContent>
                </Sheet>
            </div>

            <div className="flex-1 min-h-0">
                <AdminDataGrid
                    columns={columns}
                    data={equipments}
                    loading={loading}
                    onRowClick={(item) => {
                        setSelectedEquipment(item);
                        setIsSheetOpen(true);
                    }}
                />
            </div>

            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent className="bg-neutral-950 border-neutral-800 text-neutral-200">
                    <DialogHeader>
                        <DialogTitle>Confirmar Exclusão</DialogTitle>
                        <DialogDescription className="text-neutral-400">
                            Tem certeza que deseja excluir o equipamento <span className="text-white font-bold">{equipmentToDelete?.nome}</span>?
                            Essa ação não pode ser desfeita e pode afetar o histórico de dados.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} className="bg-transparent border-neutral-700 text-neutral-300 hover:bg-neutral-800">Cancelar</Button>
                        <Button variant="destructive" onClick={handleDelete} className="bg-red-900 hover:bg-red-800 text-white">Excluir</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

        </div>
    );
};

export default EquipmentsAdmin;
