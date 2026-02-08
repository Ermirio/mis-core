import React, { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "../ui/button";
import {
    Form,
    FormControl,
    FormDescription,
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

// Schema de Validação
const formSchema = z.object({
    nome: z.string().min(2, {
        message: "Nome deve ter pelo menos 2 caracteres.",
    }),
    codigo: z.string().min(2, {
        message: "Código deve ter pelo menos 2 caracteres.",
    }),
    tipo: z.string({
        required_error: "Selecione o tipo de equipamento.",
    }),
    linha: z.string({
        required_error: "Selecione a linha de produção.",
    }),
    velocidade_nominal: z.preprocess((val) => Number(val), z.number().min(0)),
    meta_oee: z.preprocess((val) => Number(val), z.number().min(0).max(100)),
});

interface EquipmentFormProps {
    initialData?: any;
    onSubmit: (data: z.infer<typeof formSchema>) => void;
    onCancel: () => void;
    isLoading?: boolean;
}

const EquipmentForm: React.FC<EquipmentFormProps> = ({
    initialData,
    onSubmit,
    onCancel,
    isLoading,
}) => {
    const [linhas, setLinhas] = useState<any[]>([]);

    // Carregar linhas para o Select
    useEffect(() => {
        async function fetchLinhas() {
            const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";
            try {
                const resp = await fetch(`${DJANGO_API_URL}/linhas/`);
                if (!resp.ok) throw new Error("Falha ao buscar linhas");
                const data = await resp.json();

                // Safety check: ensure we have an array
                const results = data.results || data;
                if (Array.isArray(results)) {
                    setLinhas(results);
                } else {
                    console.error("Formato de linhas inválido:", data);
                    setLinhas([]);
                }
            } catch (error) {
                console.error("Erro ao carregar linhas", error);
                setLinhas([]);
            }
        }
        fetchLinhas();
    }, []);

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            nome: initialData?.nome || "",
            codigo: initialData?.codigo || "",
            tipo: initialData?.tipo || "CLP",
            linha: initialData?.linha ? String(initialData.linha) : "",
            velocidade_nominal: initialData?.velocidade_nominal || 0,
            meta_oee: initialData?.meta_oee || 85,
        },
    });

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">

                <FormField
                    control={form.control}
                    name="nome"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel className="text-neutral-300">Nome do Equipamento</FormLabel>
                            <FormControl>
                                <Input placeholder="Ex: Enchedora Principal" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                            </FormControl>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="codigo"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Código (Tag)</FormLabel>
                                <FormControl>
                                    <Input placeholder="EQ-001" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="tipo"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Tipo</FormLabel>
                                <Select onValueChange={field.onChange} value={field.value || "CLP"}>
                                    <FormControl>
                                        <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                            <SelectValue placeholder="Selecione o tipo" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                        <SelectItem value="CLP">CLP (Controlador)</SelectItem>
                                        <SelectItem value="SENSOR_IOT">Sensor IoT</SelectItem>
                                        <SelectItem value="CAMERA">Câmera Visão</SelectItem>
                                        <SelectItem value="BALANCA">Balança</SelectItem>
                                        <SelectItem value="IMPRESSORA">Impressora</SelectItem>
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="linha"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel className="text-neutral-300">Linha de Produção</FormLabel>
                            <Select onValueChange={field.onChange} value={field.value || ""}>
                                <FormControl>
                                    <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                        <SelectValue placeholder="Selecione a linha" />
                                    </SelectTrigger>
                                </FormControl>
                                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                    {linhas.length === 0 ? (
                                        <div className="p-2 text-xs text-neutral-500 text-center">Nenhuma linha encontrada</div>
                                    ) : (
                                        linhas.map((linha) => (
                                            <SelectItem key={linha.id} value={String(linha.id)}>
                                                {linha.nome} ({linha.codigo})
                                            </SelectItem>
                                        ))
                                    )}
                                </SelectContent>
                            </Select>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="velocidade_nominal"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Vel. Nominal (un/min)</FormLabel>
                                <FormControl>
                                    <Input type="number" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="meta_oee"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Meta OEE (%)</FormLabel>
                                <FormControl>
                                    <Input type="number" step="0.1" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t border-neutral-800">
                    <Button type="button" variant="outline" onClick={onCancel} className="bg-transparent border-neutral-700 text-neutral-300 hover:bg-neutral-800 hover:text-white">
                        Cancelar
                    </Button>
                    <Button type="submit" disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {initialData ? "Salvar Alterações" : "Criar Equipamento"}
                    </Button>
                </div>
            </form>
        </Form>
    );
};

export default EquipmentForm;
