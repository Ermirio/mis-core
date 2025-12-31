import React, { useEffect, useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Activity, AlertTriangle, CheckCircle, Info, ChevronLeft, ChevronRight, Play, XCircle } from 'lucide-react';
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

interface DiagnosticAlert {
    rule: string;
    severity: 'info' | 'warning' | 'critical';
    message: string;
    details: any;
    timestamp: string;
}

interface GoldenStateProfile {
    velocidade_atual: number;
    oee_atual?: number;
    sku?: string;
    capture_type?: string;
    time: string;
    [key: string]: any;
}

interface DiagnosticsPanelProps {
    equipamentoCodigo: string;
}
const DiagnosticsPanel: React.FC<DiagnosticsPanelProps> = ({ equipamentoCodigo }) => {
    const [alerts, setAlerts] = useState<DiagnosticAlert[]>([]);
    const [goldenState, setGoldenState] = useState<GoldenStateProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [capturing, setCapturing] = useState(false);

    // Filtering State
    const [filterCurrentSku, setFilterCurrentSku] = useState(false);

    // UI Logic for History
    const [histPage, setHistPage] = useState(1);
    const HIST_ITEMS_PER_PAGE = 5;
    const [history, setHistory] = useState<GoldenStateProfile[]>([]);

    // --- ISA 101 WRITE INTERFACE STATE ---
    const [dialogOpen, setDialogOpen] = useState(false);
    const [step, setStep] = useState<'CONFIRM' | 'EXECUTING' | 'RESULT'>('CONFIRM');
    const [selectedProfile, setSelectedProfile] = useState<GoldenStateProfile | null>(null);
    const [writeStatus, setWriteStatus] = useState({
        status: 'PENDING',
        message: 'Aguardando confirmação...',
        progress: 0,
        current: 0,
        total: 0
    });
    // -------------------------------------

    const handleApplyClick = (profile: GoldenStateProfile) => {
        setSelectedProfile(profile);
        setStep('CONFIRM');
        setWriteStatus({
            status: 'PENDING',
            message: 'Aguardando confirmação...',
            progress: 0,
            current: 0,
            total: 0
        });
        setDialogOpen(true);
    };

    const confirmApply = async () => {
        if (!selectedProfile) return;

        setStep('EXECUTING');
        setWriteStatus(prev => ({ ...prev, message: 'Enviando comando para fila...', progress: 5 }));

        try {
            const response = await fetch(`${import.meta.env.VITE_FLASK_API_URL}/golden-state/apply`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    equipamento_codigo: equipamentoCodigo,
                    profile_timestamp: selectedProfile.time
                })
            });
            const data = await response.json();

            if (response.ok && data.status === 'queued') {
                const batchId = data.batch_id;

                // Polling
                const pollInterval = setInterval(async () => {
                    try {
                        const res = await fetch(`${import.meta.env.VITE_FLASK_API_URL}/golden-state/status/${batchId}`);
                        const statusData = await res.json();

                        // Parse Progress
                        let pct = 0;
                        let curr = 0;
                        let tot = statusData.progress?.total || 1;

                        if (statusData.progress) {
                            curr = statusData.progress.current;
                            tot = statusData.progress.total;
                            pct = tot > 0 ? (curr / tot) * 100 : 0;
                        }

                        if (['SUCCESS', 'ERROR', 'PARTIAL_SUCCESS'].includes(statusData.status)) {
                            clearInterval(pollInterval);
                            setWriteStatus({
                                status: statusData.status,
                                message: statusData.message,
                                progress: 100,
                                current: tot,
                                total: tot
                            });
                            setStep('RESULT');
                        } else {
                            // Update Intermediate Status
                            setWriteStatus({
                                status: 'PENDING',
                                message: statusData.message || 'Processando...',
                                progress: Math.max(5, pct), // Keep at least 5% to show activity
                                current: curr,
                                total: tot
                            });
                        }
                    } catch (e) {
                        console.error("Polling error", e);
                    }
                }, 1000);

                // Timeout Safety
                setTimeout(() => {
                    clearInterval(pollInterval);
                    setWriteStatus(prev => {
                        if (prev.status === 'PENDING') {
                            setStep('RESULT');
                            return { ...prev, status: 'ERROR', message: 'Timeout: Sem resposta do Coletor em 20s.' };
                        }
                        return prev;
                    });
                }, 20000);

            } else {
                setWriteStatus({
                    status: 'ERROR',
                    message: data.status === 'skipped' ? "Nenhum parâmetro configurado encontrado." : (data.error || 'Falha ao enfileirar.'),
                    progress: 0, current: 0, total: 0
                });
                setStep('RESULT');
            }
        } catch (error) {
            console.error("Error applying golden state:", error);
            setWriteStatus({ status: 'ERROR', message: 'Erro de conexão com servidor.', progress: 0, current: 0, total: 0 });
            setStep('RESULT');
        }
    };

    const fetchDiagnostics = async () => {
        try {
            let url = `${import.meta.env.VITE_FLASK_API_URL}/diagnostics/alerts/${equipamentoCodigo}`;
            if (filterCurrentSku) {
                url += `?current_sku_only=true`;
            }
            const response = await fetch(url);
            const data = await response.json();
            if (data.status === 'success') {
                setAlerts(data.alerts);
                setGoldenState(data.golden_state);
                setHistory(data.golden_state_history || []);
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
            const response = await fetch(`${import.meta.env.VITE_FLASK_API_URL}/diagnostics/capture/${equipamentoCodigo}`, {
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
    }, [equipamentoCodigo, filterCurrentSku]);

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical': return <AlertTriangle className="h-4 w-4 text-red-500" />;
            case 'warning': return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
            default: return <Info className="h-4 w-4 text-blue-500" />;
        }
    };

    // Helper to extract sensors
    const getSensors = () => {
        if (!goldenState) return [];
        const ignore = ['time', 'equipamento', 'sku', 'capture_type', 'velocidade_atual', 'oee_atual', 'measurement'];
        const sensors: any[] = [];
        const keys = Object.keys(goldenState).filter(k => !ignore.includes(k) && !k.endsWith('_min') && !k.endsWith('_max'));
        keys.forEach(k => {
            sensors.push({
                name: k,
                val: goldenState[k],
                min: goldenState[`${k}_min`],
                max: goldenState[`${k}_max`]
            });
        });
        return sensors;
    };

    // History Table Logic
    const histSensorKeys = useMemo(() => {
        const keys = new Set<string>();
        const ignore = ['time', 'equipamento', 'sku', 'capture_type', 'velocidade_atual', 'oee_atual', 'measurement', 'id', 'tags'];
        history.forEach(item => {
            Object.keys(item).forEach(k => {
                if (!ignore.includes(k) && !k.endsWith('_min') && !k.endsWith('_max') && !k.startsWith('last_')) {
                    keys.add(k);
                }
            });
        });
        return Array.from(keys).sort();
    }, [history]);

    const histTotalPages = Math.ceil(history.length / HIST_ITEMS_PER_PAGE);
    const histCurrentItems = history.slice((histPage - 1) * HIST_ITEMS_PER_PAGE, histPage * HIST_ITEMS_PER_PAGE);
    const sensors = getSensors();

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

            {/* ISA 101 WRITING COMPLIANT DIALOG */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Aplicar Parâmetros (Golden State)</DialogTitle>
                        <DialogDescription>
                            {step === 'CONFIRM' && "Por favor, confirme a operação de escrita no controlador."}
                            {step === 'EXECUTING' && "Aplicação em andamento. Não feche esta janela."}
                            {step === 'RESULT' && "Operação finalizada."}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="py-4">
                        {step === 'CONFIRM' && selectedProfile && (
                            <div className="space-y-4">
                                <Alert className="bg-blue-50 border-blue-200">
                                    <Info className="h-4 w-4 text-blue-500" />
                                    <AlertTitle className="text-blue-700">Resumo da Operação</AlertTitle>
                                    <AlertDescription className="text-blue-600">
                                        Você está prestes a escrever os parâmetros deste perfil na máquina.
                                    </AlertDescription>
                                </Alert>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div className="font-semibold">Horário do Perfil:</div>
                                    <div>{new Date(selectedProfile.time).toLocaleString()}</div>
                                    <div className="font-semibold">SKU:</div>
                                    <div>{selectedProfile.sku || 'N/A'}</div>
                                    <div className="font-semibold">Velocidade Alvo:</div>
                                    <div>{selectedProfile.velocidade_atual?.toFixed(0)} un/min</div>
                                </div>
                            </div>
                        )}

                        {step === 'EXECUTING' && (
                            <div className="space-y-6">
                                <div className="space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span>Progresso da Escrita</span>
                                        <span className="font-bold">{Math.round(writeStatus.progress)}%</span>
                                    </div>
                                    <Progress value={writeStatus.progress} className="h-2" />
                                </div>
                                <div className="bg-slate-950 text-slate-50 p-3 rounded-md font-mono text-xs h-24 overflow-y-auto">
                                    &gt; {writeStatus.message}<br />
                                    {writeStatus.total > 0 && `&gt; Processando item ${writeStatus.current} de ${writeStatus.total}...`}
                                </div>
                            </div>
                        )}

                        {step === 'RESULT' && (
                            <div className="space-y-4 text-center">
                                {writeStatus.status === 'SUCCESS' ? (
                                    <div className="flex flex-col items-center gap-2 text-green-600">
                                        <CheckCircle className="h-12 w-12" />
                                        <h4 className="text-lg font-bold">Sucesso!</h4>
                                        <p className="text-sm text-foreground">{writeStatus.message}</p>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center gap-2 text-red-600">
                                        <XCircle className="h-12 w-12" />
                                        <h4 className="text-lg font-bold">Falha na Escrita</h4>
                                        <p className="text-sm text-foreground">{writeStatus.message}</p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <DialogFooter className="sm:justify-between">
                        {step === 'CONFIRM' && (
                            <>
                                <Button variant="ghost" onClick={() => setDialogOpen(false)}>Cancelar</Button>
                                <Button onClick={confirmApply} className="bg-blue-600 hover:bg-blue-700 text-white">
                                    <Play className="mr-2 h-4 w-4" /> Confirmar e Aplicar
                                </Button>
                            </>
                        )}
                        {step === 'EXECUTING' && (
                            <Button disabled variant="secondary" className="w-full">
                                <Activity className="mr-2 h-4 w-4 animate-spin" /> Processando...
                            </Button>
                        )}
                        {step === 'RESULT' && (
                            <Button className="w-full" onClick={() => setDialogOpen(false)}>
                                Fechar
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Golden State Status */}
            <Card className="border-l-4 border-l-blue-500">
                <CardHeader className="pb-2">
                    <div className="flex justify-between items-start">
                        <CardTitle className="text-sm font-medium text-muted-foreground flex flex-col">
                            <span>Golden State (Baseline) - Última Captura</span>
                            {goldenState && (
                                <span className="text-xs font-normal mt-1">
                                    {new Date(goldenState.time).toLocaleString()}
                                </span>
                            )}
                        </CardTitle>
                        {goldenState && (
                            <div className="flex gap-2">
                                <Badge variant="outline">{goldenState.capture_type || 'MANUAL'}</Badge>
                                <Badge variant="secondary">{goldenState.sku || 'N/A'}</Badge>
                            </div>
                        )}
                    </div>
                </CardHeader>
                <CardContent>
                    {goldenState ? (
                        <div className="space-y-4">
                            {/* Main Metrics */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pb-4 border-b">
                                <div>
                                    <span className="text-xs text-muted-foreground uppercase">OEE</span>
                                    <div className="text-2xl font-bold text-green-600">
                                        {(goldenState.oee_atual || 0).toFixed(1)}%
                                    </div>
                                </div>
                                <div>
                                    <span className="text-xs text-muted-foreground uppercase">Velocidade</span>
                                    <div className="text-xl font-bold">
                                        {(goldenState.velocidade_atual || 0).toFixed(0)} <span className="text-sm font-normal text-muted-foreground">un/min</span>
                                    </div>
                                </div>
                            </div>

                            {/* Dynamic Sensors */}
                            {sensors.length > 0 && (
                                <div>
                                    <p className="text-xs font-semibold text-gray-500 mb-2 uppercase">Parâmetros de Sensores</p>
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                                        {sensors.map(s => (
                                            <div key={s.name} className="p-2 bg-gray-50 rounded border text-sm">
                                                <div className="font-medium capitalize mb-1">{s.name.replace(/_/g, ' ')}</div>
                                                <div className="flex justify-between items-baseline">
                                                    <span className="font-bold">{s.val?.toFixed(1)}</span>
                                                    <span className="text-xs text-gray-400">
                                                        [{s.min ?? '-'} / {s.max ?? '-'}]
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="text-sm text-muted-foreground italic py-4 text-center">
                            Nenhum perfil Golden State capturado. Capture agora para estabelecer a linha de base.
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* History Log */}
            {history.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <div className="flex justify-between items-center">
                            <CardTitle className="text-sm font-medium">Histórico de Capturas</CardTitle>
                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="filter-sku"
                                    checked={filterCurrentSku}
                                    onCheckedChange={setFilterCurrentSku}
                                />
                                <Label htmlFor="filter-sku" className="text-xs">
                                    Apenas SKU Atual
                                </Label>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border overflow-x-auto">
                            <table className="w-full text-sm text-left whitespace-nowrap">
                                <thead className="bg-muted/50 text-muted-foreground font-medium">
                                    <tr>
                                        <th className="p-2">Data/Hora</th>
                                        <th className="p-2">Tipo</th>
                                        <th className="p-2">SKU</th>
                                        <th className="p-2">OEE</th>
                                        <th className="p-2">Veloc.</th>
                                        {/* Dynamic Headers */}
                                        {histSensorKeys.map(k => (
                                            <th key={k} className="p-2 capitalize border-l border-border/50">{k.replace(/_/g, ' ')}</th>
                                        ))}
                                        <th className="p-2 border-l">Ações</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {histCurrentItems.map((h, i) => (
                                        <tr key={i} className="border-t hover:bg-muted/50 transition-colors">
                                            <td className="p-2">{new Date(h.time).toLocaleString()}</td>
                                            <td className="p-2"><Badge variant="outline" className="text-xs">{h.capture_type || 'MANUAL'}</Badge></td>
                                            <td className="p-2">{h.sku || '-'}</td>
                                            <td className="p-2">{(h.oee_atual || 0).toFixed(1)}%</td>
                                            <td className="p-2">{(h.velocidade_atual || 0).toFixed(0)}</td>
                                            {/* Dynamic Values */}
                                            {histSensorKeys.map(k => {
                                                const val = h[k];
                                                return (
                                                    <td key={k} className="p-2 border-l border-border/50">
                                                        {val !== undefined ? (typeof val === 'number' ? val.toFixed(1) : val) : '-'}
                                                    </td>
                                                );
                                            })}
                                            <td className="p-2 border-l">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-8 text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                                                    onClick={() => handleApplyClick(h)}
                                                >
                                                    Aplicar
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {/* Pagination Controls */}
                        {histTotalPages > 1 && (
                            <div className="flex justify-between items-center mt-4">
                                <span className="text-xs text-muted-foreground">
                                    Página {histPage} de {histTotalPages}
                                </span>
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setHistPage(p => Math.max(1, p - 1))}
                                        disabled={histPage === 1}
                                    >
                                        <ChevronLeft className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setHistPage(p => Math.min(histTotalPages, p + 1))}
                                        disabled={histPage === histTotalPages}
                                    >
                                        <ChevronRight className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Active Alerts */}
            <div className="space-y-2">
                {alerts.length === 0 ? (
                    <Alert className="bg-green-500/10 border-green-500/20">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <AlertTitle>Tudo Normal</AlertTitle>
                        <AlertDescription>Nenhuma anomalia detectada em relação ao Golden State.</AlertDescription>
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
