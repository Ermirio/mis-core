import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { 
  TrendingUp, 
  Activity, 
  Database, 
  Brain,
  Play,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Zap,
  BarChart3,
  Clock,
  Target
} from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

const Dashboard = ({ selectedLine, selectedTarget, selectedModel }) => {
  const [prediction, setPrediction] = useState(null)
  const [modelStatus, setModelStatus] = useState(null)
  const [opcStatus, setOpcStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [predicting, setPredicting] = useState(false)
  const [continuousStatus, setContinuousStatus] = useState(false)
  const { toast } = useToast()

  // Nova função para carregar a última predição
  const loadLastPrediction = async () => {
    if (!selectedModel) return
    try {
      const data = await api.getLastPrediction(selectedModel.id)
      setPrediction(data)
    } catch (error) {
      // É normal não encontrar predições, então não mostramos erro
      console.error('Nenhuma predição anterior encontrada:', error)
      setPrediction(null) // Limpa predições antigas
    }
  }

  useEffect(() => {
    if (selectedModel) {
      loadModelStatus()
      checkContinuousStatus()
      loadLastPrediction() // <-- CHAMA A NOVA FUNÇÃO AQUI
    }
  }, [selectedModel])

  useEffect(() => {
    if (selectedLine) {
      loadOPCStatus()
    }
  }, [selectedLine])

  const loadModelStatus = async () => {
    if (!selectedModel) return
    
    try {
      const data = await api.getModelStatus(selectedModel.id)
      setModelStatus(data)
    } catch (error) {
      console.error('Erro ao carregar status do modelo:', error)
    }
  }

  const checkContinuousStatus = async () => {
    if (!selectedModel) return
    
    try {
      const response = await api.getContinuousPredictionsStatus(selectedModel.id)
      setContinuousStatus(response.is_running) // <-- CORREÇÃO
    } catch (error) {
      console.error('Erro ao verificar status de predições contínuas:', error)
    }
  }

  const loadOPCStatus = async () => {
    if (!selectedLine) return
    
    try {
      const data = await api.getOPCLoggingStatus(selectedLine)
      setOpcStatus(data)
    } catch (error) {
      console.error('Erro ao carregar status OPC:', error)
    }
  }

  const handlePredict = async () => {
    if (!selectedModel) {
      toast({
        title: "Erro",
        description: "Selecione um modelo para fazer predição",
        variant: "destructive"
      })
      return
    }

    setPredicting(true)
    try {
      const data = await api.predictWithModel(selectedModel.id)
      setPrediction(data)
      toast({
        title: "Sucesso",
        description: "Predição realizada com sucesso"
      })
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao fazer predição",
        variant: "destructive"
      })
    } finally {
      setPredicting(false)
    }
  }

  const formatValue = (value, decimals = 4) => {
    if (value === null || value === undefined) return 'N/A'
    return typeof value === 'number' ? value.toFixed(decimals) : value
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString('pt-BR')
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'trained':
      case true:
        return 'success'
      case 'training':
        return 'warning'
      case 'error':
        return 'error'
      default:
        return 'inactive'
    }
  }

  return (
    <div className="space-y-8 gradient-bg min-h-screen p-6">
      {/* Header melhorado */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold text-gradient">
          Dashboard de Predições
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Monitore o desempenho dos seus modelos de machine learning e visualize predições em tempo real
        </p>
      </div>

      {/* Status Cards com design melhorado */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Linha Selecionada */}
        <Card className="card-interactive shadow-soft">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Linha Ativa</CardTitle>
            <Target className="h-5 w-5 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">
              {selectedLine || 'Nenhuma'}
            </div>
            <p className="text-xs text-muted-foreground">
              Linha de produção selecionada
            </p>
          </CardContent>
        </Card>

        {/* Target Selecionado */}
        <Card className="card-interactive shadow-soft">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Target Ativo</CardTitle>
            <Database className="h-5 w-5 text-info" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-info">
              {selectedTarget?.target_name || 'Nenhum'}
            </div>
            <p className="text-xs text-muted-foreground">
              {selectedTarget?.target_unit || 'Selecione um target'}
            </p>
          </CardContent>
        </Card>

        {/* Modelo Selecionado */}
        <Card className="card-interactive shadow-soft">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Modelo Ativo</CardTitle>
            <Brain className="h-5 w-5 text-accent" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-accent">
              {selectedModel?.model_name || 'Nenhum'}
            </div>
            <p className="text-xs text-muted-foreground">
              {selectedModel?.model_type || 'Selecione um modelo'}
            </p>
          </CardContent>
        </Card>

        {/* Status OPC */}
        <Card className="card-interactive shadow-soft">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Conexão OPC</CardTitle>
            <Activity className="h-5 w-5 text-warning" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              <Badge 
                variant={opcStatus?.is_logging_active ? 'default' : 'secondary'}
                className={`status-indicator ${getStatusColor(opcStatus?.is_logging_active)}`}
              >
                {opcStatus?.is_logging_active ? (
                  <CheckCircle className="h-3 w-3 mr-1" />
                ) : (
                  <AlertCircle className="h-3 w-3 mr-1" />
                )}
                {opcStatus?.is_logging_active ? 'Conectado' : 'Desconectado'}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Status da coleta de dados
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Seção Principal */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Painel de Predição */}
        <Card className="lg:col-span-2 shadow-soft">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              <span>Painel de Predição</span>
            </CardTitle>
            <CardDescription>
              Execute predições e monitore resultados em tempo real
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {selectedModel && selectedTarget ? (
              <>
                {/* Última Predição */}
                {prediction && (
                  <div className="p-6 bg-gradient-to-r from-primary/5 to-accent/5 rounded-lg border border-primary/10">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold">Última Predição</h3>
                      <Badge className="status-indicator success">
                        <Zap className="h-3 w-3 mr-1" />
                        Recente
                      </Badge>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <div className="text-sm text-muted-foreground">Valor Predito</div>
                        <div className="text-2xl font-bold text-primary">
                          {formatValue(prediction.predicted_value)} {selectedTarget.target_unit}
                        </div>
                      </div>
                      {prediction.confidence_std_dev && (
                        <div>
                          <div className="text-sm text-muted-foreground">Confiança</div>
                          <div className="text-lg font-semibold text-accent">
                            ± {formatValue(prediction.confidence_std_dev)}
                          </div>
                        </div>
                      )}
                      <div>
                        <div className="text-sm text-muted-foreground">Timestamp</div>
                        <div className="text-sm font-medium">
                          {formatDate(prediction.timestamp)}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Botão de Predição */}
                <div className="flex justify-center">
                  <Button 
                    onClick={handlePredict} 
                    disabled={predicting}
                    size="lg"
                    className="px-8 py-3 text-lg hover-lift"
                  >
                    {predicting ? (
                      <>
                        <RefreshCw className="h-5 w-5 mr-2 animate-spin" />
                        Predizendo...
                      </>
                    ) : (
                      <>
                        <Play className="h-5 w-5 mr-2" />
                        Fazer Nova Predição
                      </>
                    )}
                  </Button>
                </div>

                {/* Status de Predições Contínuas */}
                {continuousStatus && (
                  <div className="p-4 bg-success/10 border border-success/20 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <CheckCircle className="h-5 w-5 text-success" />
                      <span className="font-medium text-success-foreground">
                        Predições Contínuas Ativas
                      </span>
                    </div>
                    <p className="text-sm text-success-foreground/80 mt-1">
                      O modelo está executando predições automaticamente a cada 5 segundos
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12">
                <AlertCircle className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-semibold mb-2">Configuração Necessária</h3>
                <p className="text-muted-foreground mb-6">
                  Selecione uma linha, target e modelo para começar a fazer predições
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  <Badge variant="outline" className={selectedLine ? 'status-indicator success' : 'status-indicator inactive'}>
                    {selectedLine ? '✓' : '○'} Linha
                  </Badge>
                  <Badge variant="outline" className={selectedTarget ? 'status-indicator success' : 'status-indicator inactive'}>
                    {selectedTarget ? '✓' : '○'} Target
                  </Badge>
                  <Badge variant="outline" className={selectedModel ? 'status-indicator success' : 'status-indicator inactive'}>
                    {selectedModel ? '✓' : '○'} Modelo
                  </Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Informações do Modelo */}
        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <BarChart3 className="h-5 w-5 text-accent" />
              <span>Status do Modelo</span>
            </CardTitle>
            <CardDescription>
              Métricas de desempenho e informações
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {selectedModel && modelStatus ? (
              <>
                {/* Status de Treinamento */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Status</span>
                    <Badge className={`status-indicator ${getStatusColor(modelStatus.status)}`}>
                      {modelStatus.status === 'trained' ? 'Treinado' : 'Não Treinado'}
                    </Badge>
                  </div>
                </div>

                {/* R² Score */}
                {modelStatus.r2_score != null && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">R² Score</span>
                      <span className="text-sm font-bold">
                        {(modelStatus.r2_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <Progress 
                      value={Math.max(0, Math.min(100, modelStatus.r2_score * 100))} 
                      className="h-2"
                    />
                  </div>
                )}

                {/* MSE */}
                {modelStatus.mse != null && (
                  <div>
                    <div className="text-sm font-medium mb-1">MSE</div>
                    <div className="text-lg font-bold text-muted-foreground">
                      {formatValue(modelStatus.mse)}
                    </div>
                  </div>
                )}

                {/* Amostras de Treino */}
                <div>
                  <div className="text-sm font-medium mb-1">Amostras de Treino</div>
                  <div className="text-lg font-bold text-info">
                    {modelStatus.sample_count || 0}
                  </div>
                </div>

                {/* Último Treinamento */}
                {modelStatus.trained_at && (
                  <div>
                    <div className="text-sm font-medium mb-1">Último Treinamento</div>
                    <div className="text-sm text-muted-foreground flex items-center">
                      <Clock className="h-4 w-4 mr-1" />
                      {formatDate(modelStatus.trained_at)}
                    </div>
                  </div>
                )}

                {/* Top Features */}
                {modelStatus.feature_importances && modelStatus.feature_importances.length > 0 && (
                  <div>
                    <div className="text-sm font-medium mb-3">Principais Features</div>
                    <div className="space-y-2">
                      {modelStatus.feature_importances.slice(0, 3).map(([feature, importance]) => (
                        <div key={feature} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="truncate max-w-32" title={feature}>
                              {feature.length > 20 ? `${feature.substring(0, 20)}...` : feature}
                            </span>
                            <span className="font-medium">{(importance * 100).toFixed(1)}%</span>
                          </div>
                          <Progress value={importance * 100} className="h-1" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8">
                <Brain className="h-12 w-12 mx-auto mb-4 text-muted-foreground/50" />
                <p className="text-sm text-muted-foreground">
                  Selecione um modelo para ver as métricas de desempenho
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Ações Rápidas */}
      <Card className="shadow-soft">
        <CardHeader>
          <CardTitle>Ações Rápidas</CardTitle>
          <CardDescription>
            Acesse rapidamente as principais funcionalidades do sistema
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button 
              variant="outline" 
              className="h-20 flex flex-col items-center justify-center space-y-2 hover-lift"
              onClick={() => window.location.href = '/models'}
            >
              <Brain className="h-6 w-6" />
              <span>Gerenciar Modelos</span>
            </Button>
            
            <Button 
              variant="outline" 
              className="h-20 flex flex-col items-center justify-center space-y-2 hover-lift"
              onClick={() => window.location.href = '/prediction'}
            >
              <TrendingUp className="h-6 w-6" />
              <span>Ver Predições</span>
            </Button>
            
            <Button 
              variant="outline" 
              className="h-20 flex flex-col items-center justify-center space-y-2 hover-lift"
              onClick={() => window.location.href = '/data'}
            >
              <Database className="h-6 w-6" />
              <span>Coletar Dados</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Dashboard
