import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Zap, AlertTriangle, Gauge } from "lucide-react";

export function FactoryOverview({ data }) {
    if (!data) return null;

    const MetricCard = ({ title, value, unit, icon: Icon, status = "normal" }) => {
        const statusColors = {
            normal: "text-slate-900 dark:text-white",
            warning: "text-amber-500",
            error: "text-red-500",
            success: "text-green-500"
        };

        return (
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium text-slate-500 dark:text-slate-400">
                        {title}
                    </CardTitle>
                    <Icon className={`h-4 w-4 ${statusColors[status]}`} />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {value} <span className="text-sm font-normal text-slate-500">{unit}</span>
                    </div>
                </CardContent>
            </Card>
        );
    };

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <MetricCard
                title="Potência Total"
                value={data.total_power_kw}
                unit="kW"
                icon={Zap}
            />
            <MetricCard
                title="Eficiência Global"
                value={data.efficiency}
                unit="%"
                icon={Gauge}
                status={data.efficiency < 80 ? "warning" : "success"}
            />
            <MetricCard
                title="Alertas Ativos"
                value={data.active_alarms}
                unit=""
                icon={AlertTriangle}
                status={data.active_alarms > 0 ? "error" : "normal"}
            />
            <MetricCard
                title="Equipamentos"
                value={data.total_equipments}
                unit="Total"
                icon={Activity}
            />
        </div>
    );
}
