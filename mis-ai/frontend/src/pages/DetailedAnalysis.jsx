import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { AlertCircle, RefreshCw, Filter, Download } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

const DetailedAnalysis = () => {
    const [lines, setLines] = useState([])
    const [selectedLine, setSelectedLine] = useState('')
    const [availableNodes, setAvailableNodes] = useState([])
    const [selectedNodes, setSelectedNodes] = useState([])
    const [chartData, setChartData] = useState([])
    const [loading, setLoading] = useState(false)

    // Filtros de Data/Hora
    const [startDate, setStartDate] = useState(() => {
        const date = new Date()
        date.setDate(date.getDate() - 1)
        return date.toISOString().split('T')[0]
    })
    const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0])
    const [startTime, setStartTime] = useState('00:00')
    const [endTime, setEndTime] = useState('23:59')

    const { toast } = useToast()

    // Carregar linhas ao montar
    useEffect(() => {
        loadLines()
    }, [])

    // Carregar variáveis (nodes) quando a linha muda
    useEffect(() => {
        if (selectedLine) {
            loadNodes(selectedLine)
        } else {
            setAvailableNodes([])
            setSelectedNodes([])
        }
    }, [selectedLine])

    const loadLines = async () => {
        try {
            const data = await api.getLines()
            setLines(data)
            if (data.length > 0) setSelectedLine(data[0].name)
        } catch (error) {
            console.error('Erro ao carregar linhas:', error)
        }
    }

    const loadNodes = async (lineName) => {
        try {
            // Busca variáveis reais do backend
            const variables = await api.getOPCVariables(lineName)
            if (variables && Array.isArray(variables)) {
                // Mapeia para o formato esperado pelo componente { id, name }
                const formattedNodes = variables.map(v => ({
                    id: v.node_id,
                    name: v.variable_name || v.node_id // Fallback para node_id se não tiver nome
                }))
                setAvailableNodes(formattedNodes)
            } else {
                setAvailableNodes([])
            }
        } catch (error) {
            console.error("Erro ao carregar nodes:", error)
            setAvailableNodes([]) // Garante lista vazia em caso de erro
            toast({
                title: "Erro",
                description: "Falha ao carregar variáveis da linha.",
                variant: "destructive"
            })
        }
    }

    const handleNodeToggle = (nodeId) => {
        setSelectedNodes(prev =>
            prev.includes(nodeId)
                ? prev.filter(id => id !== nodeId)
                : [...prev, nodeId]
        )
    }

    const loadHistoryData = async () => {
        if (!selectedLine) return
        if (selectedNodes.length === 0) {
            toast({
                title: "Aviso",
                description: "Selecione pelo menos uma variável para visualizar.",
                variant: "warning"
            })
            return
        }

        setLoading(true)
        try {
            const startDateTime = new Date(startDate + 'T' + startTime + ':00')
            const endDateTime = new Date(endDate + 'T' + endTime + ':59')

            const params = {
                line_name: selectedLine,
                start_time: startDateTime.toISOString(),
                end_time: endDateTime.toISOString(),
                node_ids: selectedNodes.join(',')
            }

            const data = await api.getOPCHistory(params)

            // Formatar dados para o gráfico
            const formattedData = data.map(item => {
                const point = {
                    timestamp: new Date(item.timestamp).toLocaleString('pt-BR', {
                        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                    }),
                    originalTimestamp: new Date(item.timestamp)
                }
                // O backend retorna { timestamp: '...', 'node_id_1': val1, 'node_id_2': val2 }
                // Então podemos espalhar o restante das chaves
                Object.keys(item).forEach(key => {
                    if (key !== 'timestamp') {
                        point[key] = item[key]
                    }
                })
                return point
            }).sort((a, b) => a.originalTimestamp - b.originalTimestamp)

            setChartData(formattedData)

            if (formattedData.length === 0) {
                toast({
                    title: "Sem dados",
                    description: "Nenhum dado encontrado para o período selecionado.",
                    variant: "default"
                })
            }

        } catch (error) {
            toast({
                title: "Erro",
                description: "Erro ao carregar histórico de dados.",
                variant: "destructive"
            })
        } finally {
            setLoading(false)
        }
    }

    // Cores para as linhas do gráfico
    const colors = ['#2563eb', '#dc2626', '#16a34a', '#d97706', '#9333ea', '#0891b2']

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold">Análise Detalhada</h1>
                <p className="text-muted-foreground">
                    Visualize e compare múltiplas variáveis históricas
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Painel de Configuração (Esquerda) */}
                <Card className="lg:col-span-1">
                    <CardHeader>
                        <CardTitle className="flex items-center">
                            <Filter className="h-5 w-5 mr-2" />
                            Configuração
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Seleção de Linha */}
                        <div className="space-y-2">
                            <Label>Linha de Produção</Label>
                            <select
                                className="w-full p-2 border rounded-md bg-background"
                                value={selectedLine}
                                onChange={(e) => setSelectedLine(e.target.value)}
                            >
                                {lines.map(line => (
                                    <option key={line.id} value={line.name}>{line.name}</option>
                                ))}
                            </select>
                        </div>

                        {/* Seleção de Período */}
                        <div className="space-y-4">
                            <Label>Período de Análise</Label>
                            <div className="grid grid-cols-2 gap-2">
                                <div>
                                    <Label className="text-xs text-muted-foreground">Início</Label>
                                    <Input
                                        type="date"
                                        value={startDate}
                                        onChange={(e) => setStartDate(e.target.value)}
                                        className="text-xs"
                                    />
                                    <Input
                                        type="time"
                                        value={startTime}
                                        onChange={(e) => setStartTime(e.target.value)}
                                        className="text-xs mt-1"
                                    />
                                </div>
                                <div>
                                    <Label className="text-xs text-muted-foreground">Fim</Label>
                                    <Input
                                        type="date"
                                        value={endDate}
                                        onChange={(e) => setEndDate(e.target.value)}
                                        className="text-xs"
                                    />
                                    <Input
                                        type="time"
                                        value={endTime}
                                        onChange={(e) => setEndTime(e.target.value)}
                                        className="text-xs mt-1"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Seleção de Variáveis */}
                        <div className="space-y-2">
                            <Label>Variáveis (Nodes)</Label>
                            <ScrollArea className="h-48 border rounded-md p-2">
                                {availableNodes.length > 0 ? (
                                    availableNodes.map(node => (
                                        <div key={node.id} className="flex items-center space-x-2 mb-2">
                                            <Checkbox
                                                id={node.id}
                                                checked={selectedNodes.includes(node.id)}
                                                onCheckedChange={() => handleNodeToggle(node.id)}
                                            />
                                            <label
                                                htmlFor={node.id}
                                                className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                                title={node.id}
                                            >
                                                {node.name}
                                            </label>
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-sm text-muted-foreground text-center py-4">
                                        Nenhuma variável disponível para esta linha.
                                    </div>
                                )}
                            </ScrollArea>
                        </div>

                        <Button className="w-full" onClick={loadHistoryData} disabled={loading || !selectedLine}>
                            {loading ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                            Carregar Dados
                        </Button>
                    </CardContent>
                </Card>

                {/* Área do Gráfico (Direita) */}
                <Card className="lg:col-span-3">
                    <CardHeader>
                        <CardTitle>Visualização Gráfica</CardTitle>
                        <CardDescription>
                            {selectedNodes.length} variáveis selecionadas
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {chartData.length > 0 ? (
                            <div className="h-[500px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis
                                            dataKey="timestamp"
                                            tick={{ fontSize: 12 }}
                                            interval="preserveStartEnd"
                                            angle={-45}
                                            textAnchor="end"
                                            height={60}
                                        />
                                        <YAxis tick={{ fontSize: 12 }} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: 'rgba(255, 255, 255, 0.95)', borderRadius: '8px', border: '1px solid #ccc' }}
                                            labelStyle={{ color: '#333', fontWeight: 'bold' }}
                                        />
                                        <Legend verticalAlign="top" height={36} />
                                        {selectedNodes.map((nodeId, index) => {
                                            const nodeName = availableNodes.find(n => n.id === nodeId)?.name || nodeId
                                            return (
                                                <Line
                                                    key={nodeId}
                                                    type="monotone"
                                                    dataKey={nodeId}
                                                    name={nodeName}
                                                    stroke={colors[index % colors.length]}
                                                    strokeWidth={2}
                                                    dot={false}
                                                    connectNulls={true}
                                                />
                                            )
                                        })}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        ) : (
                            <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed rounded-lg">
                                <AlertCircle className="h-12 w-12 mb-4 opacity-20" />
                                <p>Selecione os parâmetros e clique em "Carregar Dados"</p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

export default DetailedAnalysis
