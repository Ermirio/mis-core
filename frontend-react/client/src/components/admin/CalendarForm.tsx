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
    FormDescription,
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
import { Textarea } from "../ui/textarea";
import { DJANGO_API_URL } from "@/config/api";

// Schema
const formSchema = z.object({
    data: z.string().min(10, "Data obrigatória."),
    linha: z.preprocess((val) => Number(val), z.number().min(1, "Selecione a linha.")),
    turno: z.preprocess((val) => Number(val), z.number().min(1, "Selecione o turno.")),
    programado: z.boolean().default(true),
    meta_producao_turno: z.preprocess((val) => Number(val), z.number().min(0, "Meta deve ser maior ou igual a zero.")),
    observacoes: z.string().optional(),
});

interface CalendarFormProps {
    initialData?: any;
    onSubmit: (data: any) => void;
    onCancel: () => void;
    isLoading?: boolean;
}

const CalendarForm: React.FC<CalendarFormProps> = ({
    initialData,
    onSubmit,
    onCancel,
    isLoading,
}) => {
    const [linhas, setLinhas] = useState<any[]>([]);
    const [turnos, setTurnos] = useState<any[]>([]);

    // Carregar dados auxiliares
    useEffect(() => {
        async function fetchData() {
            // Import moved to top level
            try {
                const [respLinhas, respTurnos] = await Promise.all([
                    fetch(`${DJANGO_API_URL}/linhas/`),
                    fetch(`${DJANGO_API_URL}/turnos/`),
                ]);

                const dataLinhas = await respLinhas.json();
                const dataTurnos = await respTurnos.json();

                setLinhas(dataLinhas.results || dataLinhas);
                setTurnos(dataTurnos.results || dataTurnos);
            } catch (error) {
                console.error("Erro ao carregar dados", error);
            }
        }
        fetchData();
    }, []);

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            data: initialData?.data || new Date().toISOString().split('T')[0],
            linha: initialData?.linha || 0,
            turno: initialData?.turno || 0,
            programado: initialData?.programado !== undefined ? initialData.programado : true,
            meta_producao_turno: initialData?.meta_producao_turno || 0,
            observacoes: initialData?.observacoes || "",
        },
    });

    const handleSubmit = (values: z.infer<typeof formSchema>) => {
        onSubmit(values);
    };

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">

                <div className="grid grid-cols-1 gap-4">
                    <div className="bg-slate-800/50 p-4 rounded-md border border-slate-700/50 mb-4">
                        <h3 className="text-sm font-medium text-slate-300 mb-3 block">Programação</h3>

                        <FormField
                            control={form.control}
                            name="data"
                            render={({ field }) => (
                                <FormItem className="mb-4">
                                    <div className="grid grid-cols-4 items-center gap-4">
                                        <FormLabel className="text-neutral-300 text-right">Data:</FormLabel>
                                        <FormControl className="col-span-3">
                                            <div className="flex gap-2 items-center">
                                                <Input type="date" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 max-w-[200px]" />
                                                <span className="text-xs text-neutral-500">Hoje | <span className="text-indigo-400 cursor-pointer">📅</span></span>
                                            </div>
                                        </FormControl>
                                    </div>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="linha"
                            render={({ field }) => (
                                <FormItem className="mb-4">
                                    <div className="grid grid-cols-4 items-center gap-4">
                                        <FormLabel className="text-neutral-300 text-right">Linha de Produção:</FormLabel>
                                        <div className="col-span-3 flex items-center gap-2">
                                            <Select onValueChange={field.onChange} value={String(field.value || "")}>
                                                <FormControl>
                                                    <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200 w-[200px]">
                                                        <SelectValue placeholder="---------" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                                    {linhas.map(l => (
                                                        <SelectItem key={l.id} value={String(l.id)}>{l.nome}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <div className="flex gap-1 text-neutral-500">
                                                <span className="cursor-pointer hover:text-white">✏️</span>
                                                <span className="cursor-pointer hover:text-green-500 text-green-600 font-bold">+</span>
                                                <span className="cursor-pointer hover:text-white">👁️</span>
                                            </div>
                                        </div>
                                    </div>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="turno"
                            render={({ field }) => (
                                <FormItem className="mb-4">
                                    <div className="grid grid-cols-4 items-center gap-4">
                                        <FormLabel className="text-neutral-300 text-right">Turno:</FormLabel>
                                        <div className="col-span-3 flex items-center gap-2">
                                            <Select onValueChange={field.onChange} value={String(field.value || "")}>
                                                <FormControl>
                                                    <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200 w-[200px]">
                                                        <SelectValue placeholder="---------" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                                    {turnos.map(t => (
                                                        <SelectItem key={t.id} value={String(t.id)}>{t.nome}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <div className="flex gap-1 text-neutral-500">
                                                <span className="cursor-pointer hover:text-white">✏️</span>
                                                <span className="cursor-pointer hover:text-green-500 text-green-600 font-bold">+</span>
                                                <span className="cursor-pointer hover:text-white">👁️</span>
                                            </div>
                                        </div>
                                    </div>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="programado"
                            render={({ field }) => (
                                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md p-2">
                                    <FormControl>
                                        <Checkbox
                                            checked={field.value}
                                            onCheckedChange={field.onChange}
                                            className="data-[state=checked]:bg-blue-600 border-neutral-500"
                                        />
                                    </FormControl>
                                    <div className="space-y-1 leading-none">
                                        <FormLabel className="text-neutral-200">
                                            Programado
                                        </FormLabel>
                                        <FormDescription className="text-xs text-neutral-500">
                                            Se a linha deve produzir neste dia/turno
                                        </FormDescription>
                                    </div>
                                </FormItem>
                            )}
                        />
                    </div>
                </div>

                <div className="bg-slate-800/50 p-4 rounded-md border border-slate-700/50 mb-4">
                    <h3 className="text-sm font-medium text-slate-300 mb-3 block">Metas</h3>
                    <FormField
                        control={form.control}
                        name="meta_producao_turno"
                        render={({ field }) => (
                            <FormItem>
                                <div className="grid grid-cols-4 items-start gap-4">
                                    <FormLabel className="text-neutral-300 text-right mt-2">Meta de Produção do Turno:</FormLabel>
                                    <div className="col-span-3">
                                        <FormControl>
                                            <Input type="number" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono w-[120px]" />
                                        </FormControl>
                                        <p className="text-xs text-neutral-500 mt-1">Meta de produção para este turno específico</p>
                                    </div>
                                </div>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="observacoes"
                    render={({ field }) => (
                        <FormItem>
                            <div className="flex gap-2 items-center mb-2">
                                <FormLabel className="text-neutral-300">Observações <span className="text-blue-400 text-xs cursor-pointer hover:underline">(Mostrar)</span></FormLabel>
                            </div>
                            <FormControl>
                                <Textarea {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 min-h-[60px]" />
                            </FormControl>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="flex justify-start gap-3 pt-4 border-t border-neutral-800">
                    <Button type="submit" disabled={isLoading} className="bg-sky-700 hover:bg-sky-600 text-white uppercase font-bold text-xs px-6">
                        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        SALVAR
                    </Button>
                    <Button type="button" variant="secondary" className="bg-sky-600/20 hover:bg-sky-600/30 text-sky-200 border border-sky-600/30 text-xs">
                        Salvar e adicionar outro(a)
                    </Button>
                    <Button type="button" variant="secondary" className="bg-sky-600/20 hover:bg-sky-600/30 text-sky-200 border border-sky-600/30 text-xs">
                        Salvar e continuar editando
                    </Button>
                </div>
            </form>
        </Form>
    );
};

export default CalendarForm;
