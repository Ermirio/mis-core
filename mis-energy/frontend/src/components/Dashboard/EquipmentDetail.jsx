import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, Thermometer, Gauge, Zap } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function EquipmentDetail({ equipment, history, statistics }) {
    if (!equipment) return (
        <div className="flex items-center justify-center h-64 text-slate-500">
            Selecione um equipamento para ver os detalhes
        </div>
    );

    const getStatusColor = (status) => {
        switch (status) {
            case 'running': return 'bg-green-500';
            case 'stopped': return 'bg-slate-500';
            case 'fault': return 'bg-red-500';
            default: return 'bg-slate-500';
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{equipment.name}</h2>
                    <p className="text-slate-500">{equipment.hierarchy_path}</p>
                </div>
                <Badge variant="outline" className="text-base px-4 py-1">
                    <div className={`w-2 h-2 rounded-full mr-2 ${getStatusColor('running')}`} />
                    Running
                </Badge>
            </div>

            {/* Real-time Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-500">Valor Atual</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {equipment.last_value || 0} <span className="text-sm font-normal">{equipment.unit}</span>
                        </div>
                    </CardContent>
                </Card>

                {/* Dynamic Parameters based on Type */}
                {equipment.equipment_type === 'motor' && (
                    <>
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-slate-500 flex items-center">
                                    <Gauge className="h-4 w-4 mr-2" /> RPM
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">
                                    {equipment.parameters?.rpm || 1750}
                                </div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-slate-500 flex items-center">
                                    <Zap className="h-4 w-4 mr-2" /> Potência
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">
                                    {equipment.parameters?.power_cv || 0} <span className="text-sm font-normal">CV</span>
                                </div>
                            </CardContent>
                        </Card>
                    </>
                )}
            </div>

            {/* Charts & Statistics */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Main Chart */}
                <Card className="lg:col-span-2">
                    <CardHeader>
                        <CardTitle>Tendência (24h)</CardTitle>
                    </CardHeader>
                    <CardContent className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={history}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                <XAxis
                                    dataKey="timestamp"
                                    tickFormatter={(time) => new Date(time).getHours() + 'h'}
                                    stroke="#94a3b8"
                                />
                                <YAxis stroke="#94a3b8" />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1e293b', border: 'none', color: '#fff' }}
                                    labelFormatter={(label) => new Date(label).toLocaleString()}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    dot={false}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                {/* Statistical Summary */}
                <Card>
                    <CardHeader>
                        <CardTitle>Estatísticas (24h)</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div>
                            <span className="text-sm text-slate-500 block mb-1">Média</span>
                            <div className="text-xl font-semibold">
                                {statistics?.average?.toFixed(2) || 0} {equipment.unit}
                            </div>
                            <div className="w-full bg-slate-100 rounded-full h-2 mt-2">
                                <div className="bg-blue-500 h-2 rounded-full" style={{ width: '60%' }} />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <span className="text-sm text-slate-500 block mb-1">Mínimo</span>
                                <div className="text-lg font-medium text-slate-700 dark:text-slate-300">
                                    {statistics?.minimum?.toFixed(2) || 0}
                                </div>
                            </div>
                            <div>
                                <span className="text-sm text-slate-500 block mb-1">Máximo</span>
                                <div className="text-lg font-medium text-slate-700 dark:text-slate-300">
                                    {statistics?.maximum?.toFixed(2) || 0}
                                </div>
                            </div>
                        </div>

                        <div className="pt-4 border-t">
                            <span className="text-sm text-slate-500 block mb-1">Total Acumulado</span>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">
                                {statistics?.total?.toFixed(2) || 0} <span className="text-sm font-normal">{equipment.unit}</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
