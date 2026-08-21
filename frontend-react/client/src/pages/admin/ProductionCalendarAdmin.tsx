import React, { useEffect, useState } from "react";
import { Plus, Edit, Calendar, CheckCircle, XCircle, Search } from "lucide-react";
import AdminDataGrid from "../../components/admin/AdminDataGrid";
import CalendarForm from "../../components/admin/CalendarForm";
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
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "../../components/ui/select";
import { DJANGO_API_URL } from '@/config/api';

const ProductionCalendarAdmin: React.FC = () => {

    // Grid State
    const [entries, setEntries] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize] = useState(50);

    // Filter State
    const [selectedLine, setSelectedLine] = useState<string>("all");
    const [selectedDate, setSelectedDate] = useState<string>("");
    const [linhas, setLinhas] = useState<any[]>([]);

    // CRUD State
    const [isSheetOpen, setIsSheetOpen] = useState(false);
    const [selectedEntry, setSelectedEntry] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Load Lines for Filter
    useEffect(() => {
        fetch(`${DJANGO_API_URL}/linhas/`)
            .then(res => res.json())
            .then(data => setLinhas(data.results || data))
            .catch(err => console.error("Erro ao carregar linhas", err));
    }, []);

    const fetchEntries = async (currentPage = 1) => {
        setLoading(true);
        try {
            const offset = (currentPage - 1) * pageSize;
            let url = `${DJANGO_API_URL}/calendario/?limit=${pageSize}&offset=${offset}`;

            if (selectedLine && selectedLine !== "all") {
                url += `&linha_id=${selectedLine}`;
            }
            if (selectedDate) {
                url += `&data=${selectedDate}`;
            }

            const resp = await fetch(url);
            const data = await resp.json();

            if (data.results) {
                setEntries(data.results);
                setTotal(data.count);
            } else {
                setEntries(data);
                setTotal(data.length);
            }
        } catch (error) {
            console.error("Erro ao carregar calendário", error);
            toast.error("Falha ao carregar calendário.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            fetchEntries(1);
        }, 500);
        return () => clearTimeout(timer);
    }, [selectedLine, selectedDate]);

    useEffect(() => {
        fetchEntries(page);
    }, [page]);

    const handleCreateOrUpdate = async (values: any) => {
        setIsSubmitting(true);
        try {
            const url = selectedEntry
                ? `${DJANGO_API_URL}/calendario/${selectedEntry.id}/`
                : `${DJANGO_API_URL}/calendario/`;

            const method = selectedEntry ? 'PUT' : 'POST';

            // Get CSRF token from cookie
            const getCsrfToken = (): string => {
                const match = document.cookie.match(/csrftoken=([^;]+)/);
                return match ? match[1] : '';
            };

            const resp = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                credentials: 'include',
                body: JSON.stringify(values),
            });

            if (!resp.ok) {
                const errData = await resp.json();
                throw new Error(JSON.stringify(errData));
            }

            toast.success(selectedEntry ? "Entrada atualizada!" : "Entrada criada!");
            setIsSheetOpen(false);
            fetchEntries(page);

        } catch (error: any) {
            console.error("Erro ao salvar entrada", error);
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

    const columns = [
        {
            key: "data",
            header: "Data",
            width: "120px",
            render: (item: any) => (
                <div className="flex items-center gap-2 text-neutral-200">
                    <Calendar className="w-4 h-4 text-neutral-500" />
                    <span className="font-mono">{new Date(item.data).toLocaleDateString()}</span>
                </div>
            )
        },
        {
            key: "linha_nome",
            header: "Linha",
            width: "150px",
            render: (item: any) => <span className="text-neutral-300 font-medium">{item.linha_nome}</span>
        },
        {
            key: "turno_nome",
            header: "Turno",
            width: "100px",
            render: (item: any) => <span className="text-neutral-400">{item.turno_nome}</span>
        },
        {
            key: "programado",
            header: "Status",
            width: "120px",
            render: (item: any) => item.programado ?
                <span className="inline-flex items-center gap-1 text-emerald-400 text-xs font-bold border border-emerald-900/50 bg-emerald-950/30 px-2 py-0.5 rounded"><CheckCircle className="w-3 h-3" /> Programado</span> :
                <span className="inline-flex items-center gap-1 text-neutral-500 text-xs font-bold border border-neutral-800 bg-neutral-900 px-2 py-0.5 rounded"><XCircle className="w-3 h-3" /> Sem Produção</span>
        },
        {
            key: "meta_producao_turno",
            header: "Meta Turno",
            width: "100px",
            render: (item: any) => <span className="font-mono text-neutral-200">{item.meta_producao_turno.toLocaleString()}</span>
        },
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
                        setSelectedEntry(item);
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
                        <Calendar className="w-6 h-6 text-sky-500" />
                        Calendário de Produção
                    </h2>
                    <p className="text-sm text-neutral-500">Gerenciamento de turnos e metas por dia.</p>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                    {/* Filters */}
                    <div className="flex gap-2">
                        <Select value={selectedLine} onValueChange={setSelectedLine}>
                            <SelectTrigger className="w-[180px] bg-neutral-900 border-neutral-800 text-neutral-200">
                                <SelectValue placeholder="Todas as Linhas" />
                            </SelectTrigger>
                            <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                <SelectItem value="all">Todas as Linhas</SelectItem>
                                {linhas.map(l => (
                                    <SelectItem key={l.id} value={String(l.id)}>{l.nome}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        <Input
                            type="date"
                            className="bg-neutral-900 border-neutral-800 text-neutral-200 w-[150px]"
                            value={selectedDate}
                            onChange={(e) => setSelectedDate(e.target.value)}
                        />
                    </div>

                    <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
                        <SheetTrigger asChild>
                            <Button
                                onClick={() => setSelectedEntry(null)}
                                className="bg-sky-600 hover:bg-sky-700 text-white whitespace-nowrap"
                            >
                                <Plus className="mr-2 h-4 w-4" /> Adicionar Calendário
                            </Button>
                        </SheetTrigger>
                        <SheetContent className="bg-neutral-950 border-l border-neutral-800 text-neutral-200 sm:max-w-xl">
                            <SheetHeader>
                                <SheetTitle className="text-neutral-100">
                                    {selectedEntry ? "Editar Calendário" : "Adicionar Calendário de Produção"}
                                </SheetTitle>
                                <SheetDescription className="text-neutral-500">
                                    Defina a programação e metas para um turno específico.
                                </SheetDescription>
                            </SheetHeader>
                            <div className="mt-6">
                                <CalendarForm
                                    initialData={selectedEntry}
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
                    data={entries}
                    loading={loading}
                    page={page}
                    pageSize={pageSize}
                    total={total}
                    onPageChange={setPage}
                    onRowClick={(item) => {
                        setSelectedEntry(item);
                        setIsSheetOpen(true);
                    }}
                />
            </div>
        </div>
    );
};

export default ProductionCalendarAdmin;
