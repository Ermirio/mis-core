import React, { useEffect, useState } from "react";
import { Plus, CheckCircle, XCircle, Edit, Trash2, Filter, Search } from "lucide-react";
import AdminDataGrid from "../../components/admin/AdminDataGrid";
import TagForm from "../../components/admin/TagForm";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from "../../components/ui/sheet";
import { toast } from "sonner";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "../../components/ui/dialog";

const TagsAdmin: React.FC = () => {
    const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";

    // Grid State
    const [tags, setTags] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize] = useState(50); // Ajuste conforme necessário

    // Filter State
    const [searchTerm, setSearchTerm] = useState("");

    // CRUD State
    const [isSheetOpen, setIsSheetOpen] = useState(false);
    const [selectedTag, setSelectedTag] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [tagToDelete, setTagToDelete] = useState<any | null>(null);

    const fetchTags = async (currentPage = 1, search = "") => {
        setLoading(true);
        try {
            // Construir URL com paginação e busca
            const offset = (currentPage - 1) * pageSize;
            let url = `${DJANGO_API_URL}/tags-coleta/?limit=${pageSize}&offset=${offset}`;

            if (search) {
                // Supondo que a API suporte ?search=
                url += `&search=${encodeURIComponent(search)}`;
            }

            const resp = await fetch(url);
            const data = await resp.json();

            // Suporte a paginação do DRF
            if (data.results) {
                setTags(data.results);
                setTotal(data.count);
            } else {
                setTags(data);
                setTotal(data.length);
            }
        } catch (error) {
            console.error("Erro ao carregar tags", error);
            toast.error("Falha ao carregar lista de tags.");
        } finally {
            setLoading(false);
        }
    };

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1); // Resetar para primeira página na busca
            fetchTags(1, searchTerm);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    // Pagination change
    useEffect(() => {
        fetchTags(page, searchTerm);
    }, [page]);

    const handleCreateOrUpdate = async (values: any) => {
        setIsSubmitting(true);
        try {
            const url = selectedTag
                ? `${DJANGO_API_URL}/tags-coleta/${selectedTag.id}/`
                : `${DJANGO_API_URL}/tags-coleta/`;

            const method = selectedTag ? 'PUT' : 'POST';

            const resp = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(values),
            });

            if (!resp.ok) {
                const errData = await resp.json();
                throw new Error(JSON.stringify(errData));
            }

            toast.success(selectedTag ? "Tag atualizada!" : "Tag criada!");
            setIsSheetOpen(false);
            fetchTags(page, searchTerm); // Recarregar página atual

        } catch (error: any) {
            console.error("Erro ao salvar tag", error);
            let msg = "Erro ao salvar.";
            try {
                // Tentar extrair mensagem se for JSON
                const errObj = JSON.parse(error.message);
                if (errObj.detail) msg = errObj.detail;
                else if (typeof errObj === 'object') msg = Object.values(errObj).flat().join(', ');
            } catch (e) { /* ignore */ }

            toast.error(msg);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async () => {
        if (!tagToDelete) return;

        try {
            const resp = await fetch(`${DJANGO_API_URL}/tags-coleta/${tagToDelete.id}/`, {
                method: 'DELETE',
            });
            if (!resp.ok) throw new Error("Falha ao excluir");

            toast.success("Tag excluída.");
            setDeleteDialogOpen(false);
            setTagToDelete(null);
            fetchTags(page, searchTerm);
        } catch (error) {
            console.error(error);
            toast.error("Erro ao excluir tag.");
        }
    };

    const columns = [
        { key: "id", header: "ID", width: "50px" },
        {
            key: "equipamento",
            header: "Equipamento",
            render: (item: any) => {
                // A API pode retornar ID ou objeto. Ajuste conforme serializador.
                // Se retornar ID, ideal seria ter o nome. Vamos assumir que o serializer traga dados extras ou usaremos o ID.
                // O ideal é ajustar o serializer para trazer `equipamento_nome` ou tratar aqui.
                // Como não temos acesso fácil ao nome aqui sem alterar serializer, vamos mostrar ID ou um placeholder se não vier expandido.
                // Melhoria futura: Adicionar `equipamento_nome` no serializer.
                return <span className="text-neutral-400">EQ-{item.equipamento}</span>
            }
        },
        { key: "nome_metrica", header: "Métrica", render: (item: any) => <span className="font-semibold text-neutral-200">{item.nome_metrica}</span> },
        { key: "node_id", header: "Node ID", render: (item: any) => <span className="text-xs font-mono text-neutral-500 truncate max-w-[200px] block" title={item.node_id}>{item.node_id}</span> },
        {
            key: "tipo_dado",
            header: "Tipo",
            width: "80px",
            render: (item: any) => (
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-neutral-800 border border-neutral-700 text-neutral-400 font-mono">
                    {item.tipo_dado}
                </span>
            )
        },
        {
            key: "ativa",
            header: "Ativa",
            width: "80px",
            render: (item: any) => (
                item.ativa
                    ? <span className="flex items-center text-emerald-500 text-xs"><CheckCircle className="w-3 h-3 mr-1" /> Sim</span>
                    : <span className="flex items-center text-red-500 text-xs"><XCircle className="w-3 h-3 mr-1" /> Não</span>
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
                            setSelectedTag(item);
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
                            setTagToDelete(item);
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
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h2 className="text-2xl font-semibold text-neutral-100">Tags de Coleta (OPC)</h2>
                    <p className="text-sm text-neutral-500">Mapeamento de variáveis OPC para métricas do sistema.</p>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                    <div className="relative w-full sm:w-64">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-neutral-500" />
                        <Input
                            placeholder="Buscar tags..."
                            className="pl-8 bg-neutral-900 border-neutral-800 text-neutral-200"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>

                    <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
                        <SheetTrigger asChild>
                            <Button
                                onClick={() => setSelectedTag(null)}
                                className="bg-emerald-600 hover:bg-emerald-700 text-white whitespace-nowrap"
                            >
                                <Plus className="mr-2 h-4 w-4" /> Nova Tag
                            </Button>
                        </SheetTrigger>
                        <SheetContent className="bg-neutral-950 border-l border-neutral-800 text-neutral-200 sm:max-w-md">
                            <SheetHeader>
                                <SheetTitle className="text-neutral-100">
                                    {selectedTag ? "Editar Tag" : "Nova Tag de Coleta"}
                                </SheetTitle>
                                <SheetDescription className="text-neutral-500">
                                    Configure o NodeID e a métrica associada.
                                </SheetDescription>
                            </SheetHeader>
                            <div className="mt-6">
                                <TagForm
                                    initialData={selectedTag}
                                    onSubmit={handleCreateOrUpdate}
                                    onCancel={() => setIsSheetOpen(false)}
                                    isLoading={isSubmitting}
                                />
                            </div>
                        </SheetContent>
                    </Sheet>
                </div>
            </div>

            <div className="flex-1 min-h-0">
                <AdminDataGrid
                    columns={columns}
                    data={tags}
                    loading={loading}
                    page={page}
                    pageSize={pageSize}
                    total={total}
                    onPageChange={setPage}
                    onRowClick={(item) => {
                        setSelectedTag(item);
                        setIsSheetOpen(true);
                    }}
                />
            </div>

            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent className="bg-neutral-950 border-neutral-800 text-neutral-200">
                    <DialogHeader>
                        <DialogTitle>Confirmar Exclusão</DialogTitle>
                        <DialogDescription className="text-neutral-400">
                            Tem certeza que deseja excluir a tag <span className="text-white font-bold">{tagToDelete?.nome_metrica}</span>?
                            Isso interromperá a coleta de dados para esta métrica imediatamente.
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

export default TagsAdmin;
