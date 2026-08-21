import React, { useEffect } from "react";
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
import { Checkbox } from "../ui/checkbox";
import { Loader2 } from "lucide-react";

// Schema de Validação
const formSchema = z.object({
    codigo: z.string().min(2, "Código deve ter pelo menos 2 caracteres."),
    descricao: z.string().min(3, "Descrição deve ter pelo menos 3 caracteres."),
    peso_unitario: z.preprocess((val) => Number(val), z.number().min(0, "Peso deve ser positivo.")),
    fator_conversao: z.preprocess((val) => Number(val), z.number().default(1.0)),
    ativo: z.boolean().default(true),
});

interface ProductFormProps {
    initialData?: any;
    onSubmit: (data: z.infer<typeof formSchema>) => void;
    onCancel: () => void;
    isLoading?: boolean;
}

const ProductForm: React.FC<ProductFormProps> = ({
    initialData,
    onSubmit,
    onCancel,
    isLoading,
}) => {
    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            codigo: initialData?.codigo || "",
            descricao: initialData?.descricao || "",
            peso_unitario: initialData?.peso_unitario || 0,
            fator_conversao: initialData?.fator_conversao || 1.0,
            ativo: initialData?.ativo !== undefined ? initialData.ativo : true,
        },
    });

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">

                <div className="grid grid-cols-3 gap-4">
                    <div className="col-span-1">
                        <FormField
                            control={form.control}
                            name="codigo"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="text-neutral-300">Código SKU</FormLabel>
                                    <FormControl>
                                        <Input placeholder="Ex: SKU-100" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                    </div>
                    <div className="col-span-2">
                        <FormField
                            control={form.control}
                            name="descricao"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="text-neutral-300">Descrição</FormLabel>
                                    <FormControl>
                                        <Input placeholder="Ex: Refrigerante 2L Cola" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200" />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="peso_unitario"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel className="text-neutral-300">Peso Unitário (g)</FormLabel>
                                <FormControl>
                                    <Input type="number" step="0.001" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
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
                                <div className="space-y-1">
                                    <FormControl>
                                        <Input type="number" step="0.001" {...field} className="bg-neutral-900 border-neutral-700 text-neutral-200 font-mono" />
                                    </FormControl>
                                    <p className="text-[10px] text-neutral-500">Multiplicador para caixas/fardos (Padrão: 1.0)</p>
                                </div>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <FormField
                    control={form.control}
                    name="ativo"
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
                                    Produto Ativo
                                </FormLabel>
                                <p className="text-sm text-neutral-500">
                                    Produtos inativos não aparecem em novas ordens de produção.
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
                        {initialData ? "Salvar Alterações" : "Criar Produto"}
                    </Button>
                </div>
            </form>
        </Form>
    );
};

export default ProductForm;
