import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface DiagnosticAlert {
    rule: string;
    severity: 'info' | 'warning' | 'critical';
    message: string;
    details: any;
    timestamp: string;
}

interface GoldenStateProfile {
    velocidade_atual: number;
    temperatura: number;
    pressao: number;
}

interface DiagnosticsPanelProps {
    equipamentoCodigo: string;
}

const DiagnosticsPanel: React.FC<DiagnosticsPanelProps> = ({ equipamentoCodigo }) => {
    const [alerts, setAlerts] = useState<DiagnosticAlert[]>([]);
    const [goldenState, setGoldenState] = useState<GoldenStateProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [capturing, setCapturing] = useState(false);

    const fetchDiagnostics = async () => {
        try {
            const response = await fetch(`${import.meta.env.VITE_FLASK_API_URL}/api/diagnostics/alerts/${equipamentoCodigo}`);
            const data = await response.json();
            if (data.status === 'success') {
                setAlerts(data.alerts);
                setGoldenState(data.golden_state);
            }
        } catch (error) {
            console.error("Error fetching diagnostics:", error);
        } finally {
            setLoading(false);
        }
    };

    const captureGoldenState = async () => {
        setCapturing(true);
        try {
            const response = await fetch(`${import.meta.env.VITE_FLASK_API_URL}/api/diagnostics/capture/${equipamentoCodigo}`, {
                method: 'POST'
            });
            const data = await response.json();
            if (data.status === 'success') {
                fetchDiagnostics(); // Refresh
            } else {
                alert("Failed to capture: " + data.message);
            }
        } catch (error) {
            console.error("Error capturing golden state:", error);
        } finally {
            setCapturing(false);
        }
    };

    useEffect(() => {
        fetchDiagnostics();
        const interval = setInterval(fetchDiagnostics, 10000); // Refresh every 10s
        return () => clearInterval(interval);
    }, [equipamentoCodigo]);

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical': return <AlertTriangle className="h-4 w-4 text-red-500" />;
            case 'warning': return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
            default: return <Info className="h-4 w-4 text-blue-500" />;
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    <Activity className="h-5 w-5" />
                    Diagnóstico Inteligente
                </h3>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={captureGoldenState}
                    disabled={capturing}
                >
                    {capturing ? 'Capturando...' : 'Capturar Golden State'}
                </Button>
            </div>

            {/* Golden State Status */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                        Golden State (Baseline)
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {goldenState ? (
                        <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                                <span className="text-muted-foreground">Velocidade Ideal:</span>
                                <div className="font-bold">{goldenState.velocidade_atual?.toFixed(1)} RPM</div>
                            </div>
                            {/* Add other metrics if available */}
                        </div>
                    ) : (
                        <div className="text-sm text-muted-foreground italic">
                            Nenhum perfil Golden State capturado.
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Active Alerts */}
            <div className="space-y-2">
                {alerts.length === 0 ? (
                    <Alert className="bg-green-500/10 border-green-500/20">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <AlertTitle>Tudo Normal</AlertTitle>
                        <AlertDescription>Nenhuma anomalia detectada.</AlertDescription>
                    </Alert>
                ) : (
                    alerts.map((alert, idx) => (
                        <Alert key={idx} variant={alert.severity === 'critical' ? 'destructive' : 'default'} className={alert.severity === 'warning' ? 'border-yellow-500/50 bg-yellow-500/10' : ''}>
                            {getSeverityIcon(alert.severity)}
                            <AlertTitle className="capitalize">{alert.rule}</AlertTitle>
                            <AlertDescription>
                                {alert.message}
                                <div className="text-xs text-muted-foreground mt-1">
                                    {new Date(alert.timestamp).toLocaleTimeString()}
                                </div>
                            </AlertDescription>
                        </Alert>
                    ))
                )}
            </div>
        </div>
    );
};

export default DiagnosticsPanel;
