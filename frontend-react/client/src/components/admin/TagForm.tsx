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
import { Checkbox } from "../ui/checkbox";
import { Loader2 } from "lucide-react";
import { DJANGO_API_URL } from "@/config/api";

// Schema de Validação
const formSchema = z.object({
    equipamento: z.preprocess((val) => Number(val), z.number().min(1, "Selecione um equipamento.")),
    nome_metrica: z.string().min(2, "Nome da métrica obrigatório."),
    node_id: z.string().min(2, "Node ID obrigatório."),
    tipo_dado: z.enum(["INT", "FLOAT", "STRING", "BOOL"]),
    unidade: z.string().optional(),
    fator_conversao: z.preprocess((val) => Number(val), z.number().default(1.0)),
    ativa: z.boolean().default(true),
});

interface TagFormProps {
    initialData?: any;
    onSubmit: (data: z.infer<typeof formSchema>) => void;
    onCancel: () => void;
    isLoading?: boolean;
}

const TagForm: React.FC<TagFormProps> = ({
    initialData,
    onSubmit,
    onCancel,
    isLoading,
}) => {
    const [equipamentos, setEquipamentos] = useState<any[]>([]);

    // Carregar equipamentos para o Select
    useEffect(() => {
        async function fetchEquipamentos() {
            try {
                const resp = await fetch(`${DJANGO_API_URL}/equipamentos/`);
                const data = await resp.json();
                setEquipamentos(data.results || data);
            } catch (error) {
                console.error("Erro ao carregar equipamentos", error);
            }
        }
        fetchEquipamentos();
    }, []);

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            equipamento: initialData?.equipamento || 0,
            nome_metrica: initialData?.nome_metrica || "",
            node_id: initialData?.node_id || "",
            tipo_dado: initialData?.tipo_dado || "INT",
            unidade: initialData?.unidade || "",
            fator_conversao: initialData?.fator_conversao || 1.0,
            ativa: initialData?.ativa !== undefined ? initialData.ativa : true,
        },
    });

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">

                <FormField
                    control={form.control}
                    name="equipamento"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel className="text-neutral-300">Equipamento</FormLabel>
                            <Select onValueChange={(val) => field.onChange(Number(val))} value={String(field.value || "")}>
                                <FormControl>
                                    <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                        <SelectValue placeholder="Selecione o equipamento" />
                                    </SelectTrigger>
                                </FormControl>
                                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200 h-64">
                                    {equipamentos.map((eq) => (
                                        <SelectItem key={eq.id} value={String(eq.id)}>
                                            {eq.nome} ({eq.codigo})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="nome_metrica"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Nome da Métrica</FormLabel>
                                <FormControl>
                                    <Input placeholder="Ex: velocidade_atual" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="tipo_dado"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Tipo de Dado</FormLabel>
                                <Select onValueChange={field.onChange} defaultValue={field.value}>
                                    <FormControl>
                                        <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                            <SelectValue placeholder="Tipo" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                        <SelectItem value="INT">Inteiro</SelectItem>
                                        <SelectItem value="FLOAT">Decimal</SelectItem>
                                        <SelectItem value="STRING">Texto</SelectItem>
                                        <SelectItem value="BOOL">Booleano</SelectItem>
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="node_id"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel className="text-neutral-300">Node ID (OPC UA)</FormLabel>
                            <FormControl>
                                <Input placeholder="ns=2;s=..." {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono text-xs" />
                            </FormControl>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="unidade"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Unidade (Opcional)</FormLabel>
                                <FormControl>
                                    <Input placeholder="Ex: kg, m/s" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="fator_conversao"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Fator Conversão</FormLabel>
                                <FormControl>
                                    <Input type="number" step="0.001" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="ativa"
                    render={({ field }) => (
                        <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border border-neutral-800 p-4">
                            <FormControl>
                                <Checkbox
                                    checked={field.value}
                                    onCheckedChange={field.onChange}
                                />
                            </FormControl>
                            <div className="space-y-1 leading-none">
                                <FormLabel className="text-neutral-300">
                                    Tag Ativa
                                </FormLabel>
                                <p className="text-sm text-neutral-500">
                                    Tags inativas param de ser coletadas pelo sistema.
                                </p>
                            </div>
                        </FormItem>
                    )}
                />

                <div className="flex justify-end gap-3 pt-4 border-t border-neutral-800">
                    <Button type="button" variant="outline" onClick={onCancel} className="bg-transparent border-neutral-700 text-neutral-300 hover:bg-neutral-800 hover:text-white">
                        Cancelar
                    </Button>
                    <Button type="submit" disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {initialData ? "Salvar Alterações" : "Criar Tag"}
                    </Button>
                </div>
            </form>
        </Form>
    );
};

export default TagForm;
