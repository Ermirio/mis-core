import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Activity,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Gauge,
  Clock,
  Target,
  Settings,
  Play,
  History
} from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

const PredictiveControl = ({ selectedLine }) => {
  const [activeRecommendations, setActiveRecommendations] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [applyDialogOpen, setApplyDialogOpen] = useState(false)
  const [selectedRecommendation, setSelectedRecommendation] = useState(null)
  const [viewMode, setViewMode] = useState('active') // 'active' ou 'history'
  const { toast } = useToast()

  useEffect(() => {
    if (selectedLine) {
      loadData()
      // Auto-refresh a cada 10 segundos
      const interval = setInterval(loadData, 10000)
      return () => clearInterval(interval)
    }
  }, [selectedLine, viewMode])

  const loadData = async () => {
    if (!selectedLine) return
    try {
      if (viewMode === 'active') {
        const data = await api.getActiveControlRecommendations()
        setActiveRecommendations(data || [])
      } else {
        const data = await api.getControlRecommendationsHistory({ line: selectedLine, limit: 50 })
        setHistory(data || [])
      }
    } catch (error) {
      console.error("Erro ao carregar dados:", error)
    }
  }

  const handleApplyClick = (recommendation) => {
    setSelectedRecommendation(recommendation)
    setApplyDialogOpen(true)
  }

  const handleApplyConfirm = async () => {
    if (!selectedRecommendation) return
    setLoading(true)
    try {
      await api.applyControlRecommendation(selectedRecommendation.id)
      toast({
        title: "✅ Ajuste Aplicado",
        description: `Controle "${selectedRecommendation.control_variable_name}" ajustado para ${selectedRecommendation.recommended_value.toFixed(2)}`,
      })
      setApplyDialogOpen(false)
      setSelectedRecommendation(null)
      loadData()
    } catch (error) {
      toast({
        title: "Erro ao Aplicar",
        description: error.message || "Falha ao aplicar ajuste no OPC",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status) => {
    const variants = {
      pending: { variant: 'default', icon: Clock, label: 'Pendente', color: 'text-yellow-600' },
      applied: { variant: 'default', icon: CheckCircle, label: 'Aplicado', color: 'text-green-600' },
      rejected: { variant: 'destructive', icon: AlertCircle, label: 'Rejeitado', color: 'text-red-600' },
    }
    const config = variants[status] || variants.pending
    const Icon = config.icon
    return (
      <Badge variant={config.variant} className="flex items-center space-x-1">
        <Icon className={`h-3 w-3 ${config.color}`} />
        <span>{config.label}</span>
      </Badge>
    )
  }

  const getErrorIndicator = (error) => {
    if (Math.abs(error) < 1) {
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Baixo</Badge>
    } else if (Math.abs(error) < 5) {
      return <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">Médio</Badge>
    } else {
      return <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">Alto</Badge>
    }
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
              Selecione uma linha na barra de navegação para visualizar recomendações de controle.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center space-x-3">
            <Gauge className="h-8 w-8 text-orange-600" />
            <span>Controle Preditivo</span>
          </h1>
          <p className="text-muted-foreground mt-1">
            Linha: <strong>{selectedLine}</strong> | Ajustes automáticos baseados em predições
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            variant={viewMode === 'active' ? 'default' : 'outline'}
            onClick={() => setViewMode('active')}
            className="flex items-center space-x-2"
          >
            <Activity className="h-4 w-4" />
            <span>Ativas</span>
          </Button>
          <Button
            variant={viewMode === 'history' ? 'default' : 'outline'}
            onClick={() => setViewMode('history')}
            className="flex items-center space-x-2"
          >
            <History className="h-4 w-4" />
            <span>Histórico</span>
          </Button>
        </div>
      </div>

      {/* Status Card - ISA-101 Style */}
      <Card className="border-2 border-orange-300 dark:border-orange-700 bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-950/20 dark:to-amber-950/20">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2 text-orange-700 dark:text-orange-400">
            <Settings className="h-5 w-5" />
            <span>Status do Sistema</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center space-x-3 p-3 bg-white dark:bg-gray-900 rounded-lg border">
              <Activity className="h-8 w-8 text-blue-600" />
              <div>
                <p className="text-xs text-muted-foreground">Recomendações Ativas</p>
                <p className="text-2xl font-bold">{activeRecommendations.length}</p>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-3 bg-white dark:bg-gray-900 rounded-lg border">
              <CheckCircle className="h-8 w-8 text-green-600" />
              <div>
                <p className="text-xs text-muted-foreground">Aplicadas Hoje</p>
                <p className="text-2xl font-bold">
                  {history.filter(h => h.status === 'applied' && new Date(h.created_at).toDateString() === new Date().toDateString()).length}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-3 bg-white dark:bg-gray-900 rounded-lg border">
              <Target className="h-8 w-8 text-purple-600" />
              <div>
                <p className="text-xs text-muted-foreground">Taxa de Sucesso</p>
                <p className="text-2xl font-bold">
                  {history.length > 0 
                    ? ((history.filter(h => h.status === 'applied').length / history.length) * 100).toFixed(0) 
                    : 0}%
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recomendações Ativas */}
      {viewMode === 'active' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Activity className="h-5 w-5 text-orange-600" />
              <span>Recomendações Pendentes</span>
            </CardTitle>
            <CardDescription>
              Ajustes sugeridos aguardando aprovação do operador
            </CardDescription>
          </CardHeader>
          <CardContent>
            {activeRecommendations.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <CheckCircle className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>Nenhuma recomendação pendente no momento</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Variável de Controle</TableHead>
                    <TableHead>Predição</TableHead>
                    <TableHead>Alvo</TableHead>
                    <TableHead>Erro</TableHead>
                    <TableHead>Valor Atual</TableHead>
                    <TableHead>Ajuste Sugerido</TableHead>
                    <TableHead>Novo Valor</TableHead>
                    <TableHead>Lógica</TableHead>
                    <TableHead>Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activeRecommendations.map((rec) => (
                    <TableRow key={rec.id} className="hover:bg-orange-50 dark:hover:bg-orange-950/20">
                      <TableCell className="font-medium">{rec.control_variable_name}</TableCell>
                      <TableCell>
                        <span className="font-mono text-sm">{rec.predicted_value.toFixed(2)}</span>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm font-bold text-blue-600">{rec.target_value.toFixed(2)}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-sm">{rec.error_absolute.toFixed(2)}</span>
                          {getErrorIndicator(rec.error_absolute)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm">{rec.current_value.toFixed(2)}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          {rec.recommended_adjustment > 0 ? (
                            <TrendingUp className="h-4 w-4 text-green-600" />
                          ) : (
                            <TrendingDown className="h-4 w-4 text-red-600" />
                          )}
                          <span className={`font-mono text-sm font-bold ${rec.recommended_adjustment > 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {rec.recommended_adjustment > 0 ? '+' : ''}{rec.recommended_adjustment.toFixed(2)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm font-bold text-orange-600">
                          {rec.recommended_value.toFixed(2)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={rec.control_logic === 'direct' ? 'default' : 'secondary'}>
                          {rec.control_logic === 'direct' ? '⬆️ Direta' : '⬇️ Reversa'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          onClick={() => handleApplyClick(rec)}
                          className="bg-orange-600 hover:bg-orange-700 text-white flex items-center space-x-1"
                        >
                          <Play className="h-3 w-3" />
                          <span>Aplicar</span>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Histórico */}
      {viewMode === 'history' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <History className="h-5 w-5 text-gray-600" />
              <span>Histórico de Recomendações</span>
            </CardTitle>
            <CardDescription>
              Últimas 50 recomendações processadas
            </CardDescription>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <History className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>Nenhum histórico disponível</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data/Hora</TableHead>
                    <TableHead>Variável</TableHead>
                    <TableHead>Ajuste</TableHead>
                    <TableHead>Novo Valor</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Aplicado Por</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((rec) => (
                    <TableRow key={rec.id}>
                      <TableCell className="font-mono text-xs">
                        {new Date(rec.created_at).toLocaleString('pt-BR')}
                      </TableCell>
                      <TableCell className="font-medium">{rec.control_variable_name}</TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          {rec.recommended_adjustment > 0 ? (
                            <TrendingUp className="h-4 w-4 text-green-600" />
                          ) : (
                            <TrendingDown className="h-4 w-4 text-red-600" />
                          )}
                          <span className="font-mono text-sm">
                            {rec.recommended_adjustment > 0 ? '+' : ''}{rec.recommended_adjustment.toFixed(2)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm">{rec.recommended_value.toFixed(2)}</span>
                      </TableCell>
                      <TableCell>{getStatusBadge(rec.status)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {rec.applied_by || '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Dialog de Confirmação - ISA-101 Style */}
      <AlertDialog open={applyDialogOpen} onOpenChange={setApplyDialogOpen}>
        <AlertDialogContent className="border-2 border-orange-400">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center space-x-2 text-orange-700 dark:text-orange-400">
              <AlertCircle className="h-6 w-6" />
              <span>Confirmar Aplicação de Ajuste</span>
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-3">
              {selectedRecommendation && (
                <>
                  <p className="text-base">
                    Você está prestes a aplicar o seguinte ajuste no processo:
                  </p>
                  <div className="bg-orange-50 dark:bg-orange-950/30 p-4 rounded-lg space-y-2 border border-orange-200 dark:border-orange-800">
                    <div className="flex justify-between">
                      <span className="font-semibold">Variável de Controle:</span>
                      <span className="font-mono">{selectedRecommendation.control_variable_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-semibold">Valor Atual:</span>
                      <span className="font-mono">{selectedRecommendation.current_value.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-semibold">Ajuste:</span>
                      <span className={`font-mono font-bold ${selectedRecommendation.recommended_adjustment > 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {selectedRecommendation.recommended_adjustment > 0 ? '+' : ''}{selectedRecommendation.recommended_adjustment.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between border-t pt-2">
                      <span className="font-semibold">Novo Valor:</span>
                      <span className="font-mono text-lg font-bold text-orange-600">
                        {selectedRecommendation.recommended_value.toFixed(2)}
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Este valor será escrito diretamente no OPC. Confirme se deseja prosseguir.
                  </p>
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleApplyConfirm}
              disabled={loading}
              className="bg-orange-600 hover:bg-orange-700 text-white"
            >
              {loading ? 'Aplicando...' : 'Confirmar e Aplicar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default PredictiveControl
