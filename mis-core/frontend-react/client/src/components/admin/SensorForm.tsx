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

// Schema de Validação
const formSchema = z.object({
    nome: z.string().min(2, "Nome obrigatório."),
    codigo: z.string().min(2, "Código obrigatório."),
    tipo: z.enum(["INPUT_BOOL", "INPUT_FLOAT", "INPUT_INT", "TIMER", "COUNTER", "SETPOINT", "LIMIT", "HEARTBEAT", "COMM_ERROR", "OUTRO"]), // Must match backend models.py
    tag_influxdb: z.string().min(2, "Tag InfluxDB obrigatória."),
    unidade: z.string().optional(),
    valor_min: z.preprocess((val) => {
        if (val === "" || val === null || val === undefined) return null;
        const n = Number(val);
        return isNaN(n) ? null : n;
    }, z.number().nullable().optional()),
    valor_max: z.preprocess((val) => {
        if (val === "" || val === null || val === undefined) return null;
        const n = Number(val);
        return isNaN(n) ? null : n;
    }, z.number().nullable().optional()),
    ativo: z.boolean().default(true),
});

interface SensorFormProps {
    initialData?: any;
    onSubmit: (data: z.infer<typeof formSchema>) => void;
    onCancel: () => void;
    isLoading?: boolean;
}

const SensorForm: React.FC<SensorFormProps> = ({
    initialData,
    onSubmit,
    onCancel,
    isLoading,
}) => {

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            nome: initialData?.nome || "",
            codigo: initialData?.codigo || "",
            tipo: initialData?.tipo || "INPUT_FLOAT",
            tag_influxdb: initialData?.tag_influxdb || "",
            unidade: initialData?.unidade || "",
            valor_min: initialData?.valor_min,
            valor_max: initialData?.valor_max,
            ativo: initialData?.ativo !== undefined ? initialData.ativo : true,
        },
    });

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">

                <FormField
                    control={form.control}
                    name="nome"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel className="text-neutral-300">Nome do Sensor</FormLabel>
                            <FormControl>
                                <Input placeholder="Ex: Sensor de Temperatura" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
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
                                <FormLabel className="text-neutral-300">Código</FormLabel>
                                <FormControl>
                                    <Input placeholder="S-001" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
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
                                <Select onValueChange={field.onChange} defaultValue={field.value}>
                                    <FormControl>
                                        <SelectTrigger className="bg-neutral-900 border-neutral-700 text-neutral-200">
                                            <SelectValue placeholder="Tipo" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent className="bg-neutral-900 border-neutral-800 text-neutral-200">
                                        <SelectItem value="INPUT_BOOL">Input Digital (Booleano)</SelectItem>
                                        <SelectItem value="INPUT_FLOAT">Input Analógico (Decimal)</SelectItem>
                                        <SelectItem value="INPUT_INT">Input Inteiro</SelectItem>
                                        <SelectItem value="TIMER">Temporizador (Tempo)</SelectItem>
                                        <SelectItem value="COUNTER">Contador</SelectItem>
                                        <SelectItem value="SETPOINT">Setpoint / Ajuste</SelectItem>
                                        <SelectItem value="LIMIT">Limite / Parâmetro</SelectItem>
                                        <SelectItem value="HEARTBEAT">Health Check</SelectItem>
                                        <SelectItem value="COMM_ERROR">Erro de Comunicação</SelectItem>
                                        <SelectItem value="OUTRO">Outro</SelectItem>
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="tag_influxdb"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel className="text-neutral-300">Tag InfluxDB (Measurement Field)</FormLabel>
                            <FormControl>
                                <Input placeholder="temperature_celsius" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono text-xs" />
                            </FormControl>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="grid grid-cols-3 gap-2">
                    <FormField
                        control={form.control}
                        name="unidade"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Unidade</FormLabel>
                                <FormControl>
                                    <Input placeholder="°C" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="valor_min"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Mínimo</FormLabel>
                                <FormControl>
                                    <Input type="number" step="0.1" {...field} value={field.value ?? ""} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="valor_max"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Máximo</FormLabel>
                                <FormControl>
                                    <Input type="number" step="0.1" {...field} value={field.value ?? ""} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="ativo"
                    render={({ field }) => (
                        <FormItem className="flex flex-row items-center space-x-3 space-y-0 rounded-md border border-neutral-800 p-3 bg-neutral-900/50">
                            <FormControl>
                                <Checkbox
                                    checked={field.value}
                                    onCheckedChange={field.onChange}
                                />
                            </FormControl>
                            <div className="space-y-1 leading-none">
                                <FormLabel className="text-neutral-300 cursor-pointer">
                                    Sensor Ativo
                                </FormLabel>
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
                        {initialData ? "Salvar Alterações" : "Criar Sensor"}
                    </Button>
                </div>
            </form>
        </Form>
    );
};

export default SensorForm;
