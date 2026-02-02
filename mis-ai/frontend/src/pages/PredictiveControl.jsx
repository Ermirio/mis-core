import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Activity,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Gauge,
  Clock,
  Target,
  Zap
} from 'lucide-react'
import { api } from '@/lib/api'

const PredictiveControl = ({ selectedLine }) => {
  const [recentActions, setRecentActions] = useState([])  // Últimas 10 ações
  const [liveData, setLiveData] = useState(null)  // Valores em tempo real
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (selectedLine) {
      loadData()
      // Auto-refresh a cada 5 segundos
      const interval = setInterval(loadData, 5000)
      return () => clearInterval(interval)
    }
  }, [selectedLine])

  const loadData = async () => {
    if (!selectedLine) return
    try {
      // Buscar últimas 10 ações aplicadas
      const historyData = await api.getControlRecommendationsHistory({ line: selectedLine, limit: 10 })
      setRecentActions(historyData || [])

      // O primeiro item é o mais recente (última ação aplicada)
      if (historyData && historyData.length > 0) {
        setLiveData(historyData[0])
      }
    } catch (error) {
      console.error("Erro ao carregar dados:", error)
    }
  }

  const getAdjustmentColor = (value) => {
    if (value > 0) return 'text-green-600'
    if (value < 0) return 'text-red-600'
    return 'text-gray-600'
  }

  const getAdjustmentIcon = (value) => {
    if (value > 0) return <TrendingUp className="h-4 w-4 text-green-600" />
    if (value < 0) return <TrendingDown className="h-4 w-4 text-red-600" />
    return null
  }

  if (!selectedLine) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Controle Preditivo</h1>
          <p className="text-muted-foreground">
            Sistema de ajuste automático baseado em predições de IA
          </p>
        </div>
        <Card>
          <CardContent className="text-center py-12">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhuma linha selecionada</h3>
            <p className="text-muted-foreground">
              Selecione uma linha na barra de navegação para visualizar o controle preditivo.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center space-x-3">
          <Gauge className="h-8 w-8 text-orange-600" />
          <span>Controle Preditivo</span>
        </h1>
        <p className="text-muted-foreground mt-1">
          Linha: <strong>{selectedLine}</strong> | Ajustes automáticos em tempo real
        </p>
      </div>

      {/* Live Values Card - Destaque */}
      {liveData && (
        <Card className="border-2 border-green-400 dark:border-green-600 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center space-x-2 text-green-700 dark:text-green-400">
              <Zap className="h-5 w-5" />
              <span>Valores em Tempo Real</span>
              <Badge variant="outline" className="ml-2 animate-pulse">LIVE</Badge>
            </CardTitle>
            <CardDescription>Última ação aplicada automaticamente</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-3 bg-white dark:bg-gray-900 rounded-lg border">
                <p className="text-xs text-muted-foreground mb-1">Variável</p>
                <p className="font-bold text-lg">{liveData.control_variable_name || 'N/A'}</p>
              </div>
              <div className="text-center p-3 bg-white dark:bg-gray-900 rounded-lg border">
                <p className="text-xs text-muted-foreground mb-1">Predição</p>
                <p className="font-mono text-lg font-bold text-blue-600">
                  {(liveData.predicted_value ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="text-center p-3 bg-white dark:bg-gray-900 rounded-lg border">
                <p className="text-xs text-muted-foreground mb-1">Alvo</p>
                <p className="font-mono text-lg font-bold text-purple-600">
                  {(liveData.target_value ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="text-center p-3 bg-white dark:bg-gray-900 rounded-lg border">
                <p className="text-xs text-muted-foreground mb-1">Ajuste</p>
                <div className={`font-mono text-lg font-bold flex items-center justify-center space-x-1 ${getAdjustmentColor(liveData.recommended_adjustment)}`}>
                  {getAdjustmentIcon(liveData.recommended_adjustment)}
                  <span>{liveData.recommended_adjustment > 0 ? '+' : ''}{(liveData.recommended_adjustment ?? 0).toFixed(2)}%</span>
                </div>
              </div>
              <div className="text-center p-3 bg-white dark:bg-gray-900 rounded-lg border border-orange-300">
                <p className="text-xs text-muted-foreground mb-1">Valor Aplicado</p>
                <p className="font-mono text-lg font-bold text-orange-600">
                  {(liveData.recommended_value ?? 0).toFixed(2)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Últimas 10 Ações */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Clock className="h-5 w-5 text-blue-600" />
            <span>Últimas 10 Ações Aplicadas</span>
          </CardTitle>
          <CardDescription>
            Fila de ajustes automáticos - A primeira linha é a ação mais recente
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentActions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Activity className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>Aguardando ações do sistema de controle...</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Hora</TableHead>
                  <TableHead>Variável</TableHead>
                  <TableHead>Predição</TableHead>
                  <TableHead>Alvo</TableHead>
                  <TableHead>Ajuste</TableHead>
                  <TableHead>Valor Aplicado</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentActions.map((action, index) => (
                  <TableRow
                    key={action.id}
                    className={index === 0 ? 'bg-green-50 dark:bg-green-950/20 border-l-4 border-l-green-500' : ''}
                  >
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      {index === 0 ? <Badge className="bg-green-600">NOVA</Badge> : index + 1}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {new Date(action.timestamp).toLocaleTimeString('pt-BR')}
                    </TableCell>
                    <TableCell className="font-medium">
                      {action.control_variable_name || 'N/A'}
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {(action.predicted_value ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell className="font-mono text-sm font-bold text-purple-600">
                      {(action.target_value ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <div className={`flex items-center space-x-1 ${getAdjustmentColor(action.recommended_adjustment)}`}>
                        {getAdjustmentIcon(action.recommended_adjustment)}
                        <span className="font-mono text-sm font-bold">
                          {action.recommended_adjustment > 0 ? '+' : ''}{(action.recommended_adjustment ?? 0).toFixed(2)}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm font-bold text-orange-600">
                      {(action.recommended_value ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Aplicado
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default PredictiveControl
