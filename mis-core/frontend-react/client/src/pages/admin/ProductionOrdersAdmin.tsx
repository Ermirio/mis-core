import React, { useEffect, useState } from "react";
import { Plus, Edit, ClipboardList, Search, Calendar, CheckCircle, PauseCircle, PlayCircle, XCircle } from "lucide-react";
import AdminDataGrid from "../../components/admin/AdminDataGrid";
import OrderForm from "../../components/admin/OrderForm";
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
import { Progress } from "../../components/ui/progress";

const ProductionOrdersAdmin: React.FC = () => {
    const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";

    // Grid State
    const [orders, setOrders] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize] = useState(50);

    // Filter State
    const [searchTerm, setSearchTerm] = useState("");

    // CRUD State
    const [isSheetOpen, setIsSheetOpen] = useState(false);
    const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const fetchOrders = async (currentPage = 1, search = "") => {
        setLoading(true);
        try {
            const offset = (currentPage - 1) * pageSize;
            let url = `${DJANGO_API_URL}/ordens-producao/?limit=${pageSize}&offset=${offset}`;

            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }

            const resp = await fetch(url);
            const data = await resp.json();

            if (data.results) {
                setOrders(data.results);
                setTotal(data.count);
            } else {
                setOrders(data);
                setTotal(data.length);
            }
        } catch (error) {
            console.error("Erro ao carregar OPs", error);
            toast.error("Falha ao carregar lista de OPs.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            fetchOrders(1, searchTerm);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    useEffect(() => {
        fetchOrders(page, searchTerm);
    }, [page]);

    const handleCreateOrUpdate = async (values: any) => {
        setIsSubmitting(true);
        try {
            const url = selectedOrder
                ? `${DJANGO_API_URL}/ordens-producao/${selectedOrder.id}/`
                : `${DJANGO_API_URL}/ordens-producao/`;

            const method = selectedOrder ? 'PUT' : 'POST';

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

            toast.success(selectedOrder ? "OP atualizada!" : "OP criada!");
            setIsSheetOpen(false);
            fetchOrders(page, searchTerm);

        } catch (error: any) {
            console.error("Erro ao salvar OP", error);
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

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'PRODUZINDO': return <span className="inline-flex items-center gap-1 text-emerald-400 text-xs font-bold border border-emerald-900/50 bg-emerald-950/30 px-2 py-0.5 rounded"><PlayCircle className="w-3 h-3" /> Produzindo</span>;
            case 'PLANEJADA': return <span className="inline-flex items-center gap-1 text-blue-400 text-xs font-bold border border-blue-900/50 bg-blue-950/30 px-2 py-0.5 rounded"><Calendar className="w-3 h-3" /> Planejada</span>;
            case 'PAUSADA': return <span className="inline-flex items-center gap-1 text-orange-400 text-xs font-bold border border-orange-900/50 bg-orange-950/30 px-2 py-0.5 rounded"><PauseCircle className="w-3 h-3" /> Pausada</span>;
            case 'CONCLUIDA': return <span className="inline-flex items-center gap-1 text-neutral-400 text-xs font-bold border border-neutral-800 bg-neutral-900 px-2 py-0.5 rounded"><CheckCircle className="w-3 h-3" /> Concluída</span>;
            case 'CANCELADA': return <span className="inline-flex items-center gap-1 text-red-500 text-xs font-bold border border-red-900/50 bg-red-950/30 px-2 py-0.5 rounded"><XCircle className="w-3 h-3" /> Cancelada</span>;
            default: return status;
        }
    }

    const columns = [
        { key: "codigo", header: "OP", width: "100px", render: (item: any) => <span className="font-mono text-neutral-200 font-bold">{item.codigo}</span> },
        {
            key: "produto_codigo",
            header: "Produto",
            render: (item: any) => (
                <div className="flex flex-col">
                    <span className="font-mono text-xs text-indigo-400">{item.produto_codigo}</span>
                    <span className="text-[10px] text-neutral-500 truncate max-w-[150px]">{item.produto_descricao}</span>
                </div>
            )
        },
        { key: "linha_nome", header: "Linha", width: "120px", render: (item: any) => <span className="text-neutral-400 text-xs">{item.linha_nome}</span> },
        { key: "meta_total", header: "Meta", width: "80px", render: (item: any) => <span className="font-mono text-neutral-300">{item.meta_total}</span> },
        {
            key: "percentual_conclusao",
            header: "Progresso",
            width: "150px",
            render: (item: any) => (
                <div className="w-full">
                    <div className="flex justify-between text-[10px] mb-1">
                        <span className="text-neutral-500">{Number(item.producao_total || 0).toLocaleString()} un</span>
                        <span className="text-neutral-300">{item.percentual_conclusao?.toFixed(1)}%</span>
                    </div>
                    <Progress value={item.percentual_conclusao || 0} className="h-1.5 bg-neutral-800" indicatorClassName={item.percentual_conclusao >= 100 ? "bg-emerald-500" : "bg-indigo-500"} />
                </div>
            )
        },
        { key: "status", header: "Status", width: "110px", render: (item: any) => getStatusBadge(item.status) },
        {
            key: "actions",
            header: "Ações",
            width: "60px",
            render: (item: any) => (
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-neutral-400 hover:text-white hover:bg-neutral-800"
                    onClick={(e) => {
                        e.stopPropagation();
                        setSelectedOrder(item);
                        setIsSheetOpen(true);
                    }}
                >
                    <Edit className="h-4 w-4" />
                </Button>
            )
        }
    ];

    return (
        <div className="h-full flex flex-col space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h2 className="text-2xl font-semibold text-neutral-100 flex items-center gap-2">
                        <ClipboardList className="w-6 h-6 text-emerald-500" />
                        Ordens de Produção
                    </h2>
                    <p className="text-sm text-neutral-500">Planejamento e acompanhamento das OPs.</p>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                    <div className="relative w-full sm:w-64">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-neutral-500" />
                        <Input
                            placeholder="Buscar OPs..."
                            className="pl-8 bg-neutral-900 border-neutral-800 text-neutral-200"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>

                    <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
                        <SheetTrigger asChild>
                            <Button
                                onClick={() => setSelectedOrder(null)}
                                className="bg-emerald-600 hover:bg-emerald-700 text-white whitespace-nowrap"
                            >
                                <Plus className="mr-2 h-4 w-4" /> Nova Ordem
                            </Button>
                        </SheetTrigger>
                        <SheetContent className="bg-neutral-950 border-l border-neutral-800 text-neutral-200 sm:max-w-md">
                            <SheetHeader>
                                <SheetTitle className="text-neutral-100">
                                    {selectedOrder ? "Editar Ordem" : "Nova Ordem de Produção"}
                                </SheetTitle>
                                <SheetDescription className="text-neutral-500">
                                    Planejamento de produção para uma linha e produto.
                                </SheetDescription>
                            </SheetHeader>
                            <div className="mt-6">
                                <OrderForm
                                    initialData={selectedOrder}
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
                    data={orders}
                    loading={loading}
                    page={page}
                    pageSize={pageSize}
                    total={total}
                    onPageChange={setPage}
                    onRowClick={(item) => {
                        setSelectedOrder(item);
                        setIsSheetOpen(true);
                    }}
                />
            </div>
        </div>
    );
};

export default ProductionOrdersAdmin;
