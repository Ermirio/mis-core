import * as React from "react"
import { addDays, addHours, format, startOfDay, subDays, subHours } from "date-fns"
import { Calendar as CalendarIcon } from "lucide-react"
import { DateRange } from "react-day-picker"
import { cn } from "@/utils/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"

interface DatePickerWithRangeProps {
    className?: string
    date?: DateRange
    setDate: (date: DateRange | undefined) => void
}

export function DatePickerWithRange({
    className,
    date,
    setDate,
}: DatePickerWithRangeProps) {
    const presets = [
        { label: 'Última 1h', getValue: () => ({ from: subHours(new Date(), 1), to: new Date() }) },
        { label: 'Últimas 6h', getValue: () => ({ from: subHours(new Date(), 6), to: new Date() }) },
        { label: 'Últimas 12h', getValue: () => ({ from: subHours(new Date(), 12), to: new Date() }) },
        { label: 'Últimas 24h', getValue: () => ({ from: subHours(new Date(), 24), to: new Date() }) },
        { label: 'Hoje', getValue: () => ({ from: startOfDay(new Date()), to: new Date() }) },
        { label: 'Ontem', getValue: () => ({ from: startOfDay(subDays(new Date(), 1)), to: startOfDay(new Date()) }) },
        { label: 'Últimos 7 dias', getValue: () => ({ from: subDays(new Date(), 7), to: new Date() }) },
    ];

    return (
        <div className={cn("grid gap-2", className)}>
            <Popover>
                <PopoverTrigger asChild>
                    <Button
                        id="date"
                        variant={"outline"}
                        className={cn(
                            "w-[300px] justify-start text-left font-normal",
                            !date && "text-muted-foreground"
                        )}
                    >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {date?.from ? (
                            date.to ? (
                                <>
                                    {format(date.from, "dd/MM/yyyy HH:mm")} -{" "}
                                    {format(date.to, "dd/MM/yyyy HH:mm")}
                                </>
                            ) : (
                                format(date.from, "dd/MM/yyyy HH:mm")
                            )
                        ) : (
                            <span>Selecione um período</span>
                        )}
                    </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                    <div className="flex">
                        <div className="border-r p-2 space-y-1">
                            {presets.map((preset) => (
                                <Button
                                    key={preset.label}
                                    variant="ghost"
                                    className="w-full justify-start text-sm"
                                    onClick={() => setDate(preset.getValue())}
                                >
                                    {preset.label}
                                </Button>
                            ))}
                        </div>
                        <Calendar
                            initialFocus
                            mode="range"
                            defaultMonth={date?.from}
                            selected={date}
                            onSelect={(range) => {
                                setDate(range);
                            }}
                            numberOfMonths={2}
                        />
                    </div>
                </PopoverContent>
            </Popover>
        </div>
    )
}
