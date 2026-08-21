import React, { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "../ui/button";
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "../ui/form";
import { Input } from "../ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "../ui/select";
import { Loader2 } from "lucide-react";
import { Textarea } from "../ui/textarea";
import { DJANGO_API_URL } from "@/config/api";

// Schema
const formSchema = z.object({
    codigo: z.string().min(3, "Código da OP obrigatório."),
    linha: z.preprocess((val) => Number(val), z.number().min(1, "Selecione a linha.")),
    produto: z.preprocess((val) => Number(val), z.number().min(1, "Selecione o produto.")),
    meta_total: z.preprocess((val) => Number(val), z.number().min(1, "Meta deve ser maior que zero.")),
    eficiencia_planejada: z.preprocess((val) => Number(val), z.number().min(0).max(100)),
    status: z.enum(["PLANEJADA", "PRODUZINDO", "PAUSADA", "CONCLUIDA", "CANCELADA"]),
    data_planejada_inicio: z.string().min(10, "Data obrigatória."),
    hora_planejada_inicio: z.string().min(5, "Hora obrigatória."), // Auxiliar para datetime
    descricao: z.string().optional(),
});

interface OrderFormProps {
    initialData?: any;
    onSubmit: (data: any) => void;
    onCancel: () => void;
    isLoading?: boolean;
}

const OrderForm: React.FC<OrderFormProps> = ({
    initialData,
    onSubmit,
    onCancel,
    isLoading,
}) => {
    const [linhas, setLinhas] = useState<any[]>([]);
    const [produtos, setProdutos] = useState<any[]>([]);
    const [selectedProduct, setSelectedProduct] = useState<any | null>(null);

    // Carregar dados auxiliares
    useEffect(() => {
        async function fetchData() {
            // Import moved to top level
            try {
                const [respLinhas, respProdutos] = await Promise.all([
                    fetch(`${DJANGO_API_URL}/linhas/`),
                    fetch(`${DJANGO_API_URL}/produtos/`),
                ]);

                const dataLinhas = await respLinhas.json();
                const dataProdutos = await respProdutos.json();

                setLinhas(dataLinhas.results || dataLinhas);
                setProdutos(dataProdutos.results || dataProdutos);
            } catch (error) {
                console.error("Erro ao carregar dados", error);
            }
        }
        fetchData();
    }, []);

    // Form setup
    const defaultDate = initialData?.data_planejada_inicio
        ? new Date(initialData.data_planejada_inicio).toISOString().split('T')[0]
        : new Date().toISOString().split('T')[0];

    const defaultTime = initialData?.data_planejada_inicio
        ? new Date(initialData.data_planejada_inicio).toTimeString().slice(0, 5)
        : "06:00";

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            codigo: initialData?.codigo || "",
            linha: initialData?.linha || 0,
            produto: initialData?.produto || 0,
            meta_total: initialData?.meta_total || 10000,
            eficiencia_planejada: initialData?.eficiencia_planejada || 85,
            status: initialData?.status || "PLANEJADA",
            data_planejada_inicio: defaultDate,
            hora_planejada_inicio: defaultTime,
            descricao: initialData?.descricao || "",
        },
    });

    // Atualizar info do produto selecionado (para mostrar peso/formato)
    const watchedProdutoId = form.watch("produto");
    useEffect(() => {
        if (watchedProdutoId) {
            const prod = produtos.find(p => p.id === Number(watchedProdutoId));
            setSelectedProduct(prod);
        }
    }, [watchedProdutoId, produtos]);

    const handleSubmit = (values: z.infer<typeof formSchema>) => {
        // Combinar data e hora para ISO string
        const combinedDate = new Date(`${values.data_planejada_inicio}T${values.hora_planejada_inicio}:00`);

        const payload = {
            ...values,
            data_planejada_inicio: combinedDate.toISOString(),
            // Campos automáticos baseados no produto, se necessário (mas o backend já lida com IDs)
            formato_gramas: selectedProduct?.peso_unitario || 0, // Fallback se backend exigir
        };

        onSubmit(payload);
    };

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="codigo"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Código OP</FormLabel>
                                <FormControl>
                                    <Input placeholder="OP-2024-001" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="status"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Status</FormLabel>
                                <Select onValueChange={field.onChange} defaultValue={field.value}>
                                    <FormControl>
                                        <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                            <SelectValue placeholder="Status" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                        <SelectItem value="PLANEJADA">Planejada</SelectItem>
                                        <SelectItem value="PRODUZINDO">Em Produção</SelectItem>
                                        <SelectItem value="PAUSADA">Pausada</SelectItem>
                                        <SelectItem value="CONCLUIDA">Concluída</SelectItem>
                                        <SelectItem value="CANCELADA">Cancelada</SelectItem>
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="linha"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Linha</FormLabel>
                                <Select onValueChange={field.onChange} value={String(field.value || "")}>
                                    <FormControl>
                                        <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                            <SelectValue placeholder="Selecione a linha" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                        {linhas.map(l => (
                                            <SelectItem key={l.id} value={String(l.id)}>{l.nome}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="produto"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Produto (SKU)</FormLabel>
                                <Select onValueChange={(val) => field.onChange(Number(val))} value={String(field.value || "")}>
                                    <FormControl>
                                        <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                            <SelectValue placeholder="Selecione o produto" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200 h-64">
                                        {produtos.map(p => (
                                            <SelectItem key={p.id} value={String(p.id)}>
                                                {p.codigo} - {p.descricao}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                {selectedProduct && (
                    <div className="text-xs text-neutral-500 bg-neutral-900/50 p-2 rounded border border-neutral-800">
                        INFO SKU: {selectedProduct.descricao} | Peso: {selectedProduct.peso_unitario}g
                    </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="meta_total"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Meta Total (Un)</FormLabel>
                                <FormControl>
                                    <Input type="number" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="eficiencia_planejada"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Eficiência Planejada (%)</FormLabel>
                                <FormControl>
                                    <Input type="number" step="0.1" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="data_planejada_inicio"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Data Início</FormLabel>
                                <FormControl>
                                    <Input type="date" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="hora_planejada_inicio"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Hora Início</FormLabel>
                                <FormControl>
                                    <Input type="time" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="descricao"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel className="text-neutral-300">Observações</FormLabel>
                            <FormControl>
                                <Textarea {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 min-h-[80px]" />
                            </FormControl>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="flex justify-end gap-3 pt-4 border-t border-neutral-800">
                    <Button type="button" variant="outline" onClick={onCancel} className="bg-transparent border-neutral-700 text-neutral-300 hover:bg-neutral-800 hover:text-white">
                        Cancelar
                    </Button>
                    <Button type="submit" disabled={isLoading} className="bg-indigo-600 hover:bg-indigo-700 text-white">
                        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {initialData ? "Salvar Alterações" : "Criar Ordem"}
                    </Button>
                </div>
            </form>
        </Form>
    );
};

export default OrderForm;
