import React, { useState } from "react";
import { Plus, Edit, Trash2, Tag, RefreshCw } from "lucide-react";
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
import TagForm from "./TagForm";
import { DJANGO_API_URL } from "@/config/api";

interface TagInlineManagerProps {
    equipmentId: number;
    tags: any[];
    onUpdate: () => void; // Callback to refresh parent data
}

const TagInlineManager: React.FC<TagInlineManagerProps> = ({ equipmentId, tags, onUpdate }) => {

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [selectedTag, setSelectedTag] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Initial data for the form - forcing the current equipment
    const getInitialData = () => {
        if (selectedTag) return selectedTag;
        return {
            equipamento: equipmentId,
            ativa: true,
            fator_conversao: 1.0,
            tipo_dado: "INT"
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
            // Force equipment ID just in case
            const payload = { ...values, equipamento: equipmentId };

            const url = selectedTag
                ? `${DJANGO_API_URL}/tags-coleta/${selectedTag.id}/`
                : `${DJANGO_API_URL}/tags-coleta/`;

            const method = selectedTag ? 'PUT' : 'POST';
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

            toast.success(selectedTag ? "Tag atualizada!" : "Tag adicionada!");
            setIsDialogOpen(false);
            onUpdate(); // Refresh parent to get updated list

        } catch (error: any) {
            console.error("Erro ao salvar tag", error);
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

    const handleDelete = async (tag: any) => {
        if (!confirm(`Tem certeza que deseja remover a tag "${tag.node_id}"?`)) return;

        try {
            const csrftoken = getCookie('csrftoken');
            const resp = await fetch(`${DJANGO_API_URL}/tags-coleta/${tag.id}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': csrftoken || '',
                },
            });

            if (!resp.ok) throw new Error("Falha ao deletar");

            toast.success("Tag removida!");
            onUpdate();
        } catch (error) {
            console.error("Erro ao deletar tag", error);
            toast.error("Erro ao remover tag.");
        }
    };

    return (
        <div className="space-y-4 border border-neutral-800 rounded-md p-4 bg-neutral-900/20">
            <div className="flex items-center justify-between">
                <h3 className="text-md font-medium text-neutral-200 flex items-center gap-2">
                    <Tag className="w-4 h-4 text-indigo-500" />
                    Tags de Coleta ({tags.length})
                </h3>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={onUpdate} className="h-8 bg-transparent border-neutral-700 hover:bg-neutral-800 text-neutral-400">
                        <RefreshCw className="w-3 h-3" />
                    </Button>
                    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                        <DialogTrigger asChild>
                            <Button
                                size="sm"
                                onClick={() => setSelectedTag(null)}
                                className="h-8 bg-indigo-600 hover:bg-indigo-700 text-white"
                            >
                                <Plus className="mr-1 h-3 w-3" /> Adicionar Tag
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-neutral-950 border-neutral-800 text-neutral-200 sm:max-w-md">
                            <DialogHeader>
                                <DialogTitle className="text-neutral-100">
                                    {selectedTag ? "Editar Tag" : "Nova Tag de Coleta"}
                                </DialogTitle>
                                <DialogDescription className="text-neutral-500">
                                    Configure o Node ID e a métrica para este equipamento.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="mt-4">
                                <TagForm
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

            {tags.length === 0 ? (
                <div className="text-center py-8 text-neutral-500 text-sm border-2 border-dashed border-neutral-800 rounded-lg">
                    Nenhuma tag configurada para este equipamento.
                </div>
            ) : (
                <div className="rounded-md border border-neutral-800 overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-neutral-900 text-neutral-400 font-medium">
                            <tr>
                                <th className="px-4 py-2">Node ID</th>
                                <th className="px-4 py-2">Métrica</th>
                                <th className="px-4 py-2">Tipo</th>
                                <th className="px-4 py-2">Status</th>
                                <th className="px-4 py-2 text-right">Ações</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-800">
                            {tags.map((tag) => (
                                <tr key={tag.id} className="hover:bg-neutral-800/50 group">
                                    <td className="px-4 py-2 font-mono text-xs text-neutral-300 truncate max-w-[200px]" title={tag.node_id}>{tag.node_id}</td>
                                    <td className="px-4 py-2 text-emerald-400">{tag.nome_metrica}</td>
                                    <td className="px-4 py-2"><span className="text-[10px] bg-neutral-800 px-1 rounded border border-neutral-700">{tag.tipo_dado}</span></td>
                                    <td className="px-4 py-2">
                                        {tag.ativa
                                            ? <span className="text-emerald-500 text-[10px] border border-emerald-900/50 bg-emerald-950/30 px-1.5 py-0.5 rounded">Ativa</span>
                                            : <span className="text-neutral-500 text-[10px] border border-neutral-800 bg-neutral-900 px-1.5 py-0.5 rounded">Inativa</span>}
                                    </td>
                                    <td className="px-4 py-2 text-right">
                                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 text-neutral-400 hover:text-white hover:bg-neutral-700"
                                                onClick={() => { setSelectedTag(tag); setIsDialogOpen(true); }}
                                            >
                                                <Edit className="h-3 w-3" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 text-neutral-400 hover:text-red-400 hover:bg-red-950/30"
                                                onClick={() => handleDelete(tag)}
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

export default TagInlineManager;
