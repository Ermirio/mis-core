import React, { useEffect, useState } from "react";
import { Plus, Edit, Package, Search } from "lucide-react";
import AdminDataGrid from "../../components/admin/AdminDataGrid";
import ProductForm from "../../components/admin/ProductForm";
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
import { DJANGO_API_URL } from '@/config/api';

const ProductsAdmin: React.FC = () => {

    // Grid State
    const [products, setProducts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize] = useState(50);

    // Filter State
    const [searchTerm, setSearchTerm] = useState("");

    // CRUD State
    const [isSheetOpen, setIsSheetOpen] = useState(false);
    const [selectedProduct, setSelectedProduct] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const fetchProducts = async (currentPage = 1, search = "") => {
        setLoading(true);
        try {
            const offset = (currentPage - 1) * pageSize;
            let url = `${DJANGO_API_URL}/produtos/?limit=${pageSize}&offset=${offset}`;

            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }

            const resp = await fetch(url);
            const data = await resp.json();

            if (data.results) {
                setProducts(data.results);
                setTotal(data.count);
            } else {
                setProducts(data);
                setTotal(data.length);
            }
        } catch (error) {
            console.error("Erro ao carregar produtos", error);
            toast.error("Falha ao carregar lista de produtos.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            fetchProducts(1, searchTerm);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    useEffect(() => {
        fetchProducts(page, searchTerm);
    }, [page]);

    const handleCreateOrUpdate = async (values: any) => {
        setIsSubmitting(true);
        try {
            const url = selectedProduct
                ? `${DJANGO_API_URL}/produtos/${selectedProduct.id}/`
                : `${DJANGO_API_URL}/produtos/`;

            const method = selectedProduct ? 'PUT' : 'POST';

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

            toast.success(selectedProduct ? "Produto atualizado!" : "Produto criado!");
            setIsSheetOpen(false);
            fetchProducts(page, searchTerm);

        } catch (error: any) {
            console.error("Erro ao salvar produto", error);
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
        { key: "codigo", header: "Código", width: "120px", render: (item: any) => <span className="font-mono text-emerald-400 font-bold">{item.codigo}</span> },
        { key: "descricao", header: "Descrição", render: (item: any) => <span className="text-neutral-200">{item.descricao}</span> },
        { key: "peso_unitario", header: "Peso (g)", width: "100px", render: (item: any) => <span className="font-mono text-neutral-400">{item.peso_unitario} g</span> },
        {
            key: "ativo",
            header: "Status",
            width: "100px",
            render: (item: any) => (
                item.ativo
                    ? <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-900/30 text-emerald-500 border border-emerald-900/50">Ativo</span>
                    : <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-900/30 text-red-500 border border-red-900/50">Inativo</span>
            )
        },
        {
            key: "actions",
            header: "Ações",
            width: "80px",
            render: (item: any) => (
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-neutral-400 hover:text-white hover:bg-neutral-800"
                    onClick={(e) => {
                        e.stopPropagation();
                        setSelectedProduct(item);
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
                        <Package className="w-6 h-6 text-indigo-500" />
                        Produtos (SKUs)
                    </h2>
                    <p className="text-sm text-neutral-500">Gerenciamento de SKUs e parâmetros de produto.</p>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                    <div className="relative w-full sm:w-64">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-neutral-500" />
                        <Input
                            placeholder="Buscar produtos..."
                            className="pl-8 bg-neutral-900 border-neutral-800 text-neutral-200"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>

                    <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
                        <SheetTrigger asChild>
                            <Button
                                onClick={() => setSelectedProduct(null)}
                                className="bg-indigo-600 hover:bg-indigo-700 text-white whitespace-nowrap"
                            >
                                <Plus className="mr-2 h-4 w-4" /> Novo Produto
                            </Button>
                        </SheetTrigger>
                        <SheetContent className="bg-neutral-950 border-l border-neutral-800 text-neutral-200 sm:max-w-md">
                            <SheetHeader>
                                <SheetTitle className="text-neutral-100">
                                    {selectedProduct ? "Editar Produto" : "Novo Produto"}
                                </SheetTitle>
                                <SheetDescription className="text-neutral-500">
                                    Defina o código, descrição e peso do SKU.
                                </SheetDescription>
                            </SheetHeader>
                            <div className="mt-6">
                                <ProductForm
                                    initialData={selectedProduct}
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
                    data={products}
                    loading={loading}
                    page={page}
                    pageSize={pageSize}
                    total={total}
                    onPageChange={setPage}
                    onRowClick={(item) => {
                        setSelectedProduct(item);
                        setIsSheetOpen(true);
                    }}
                />
            </div>
        </div>
    );
};

export default ProductsAdmin;
