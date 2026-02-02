// ===================================================================================
// ARQUIVO: PredictionView.jsx
// DESCRIÇÃO: Componente React para visualizar predições de modelos de machine learning.
//            Inclui um gráfico de séries temporais, cards de status e controles
//            para executar predições e filtrar dados históricos.
// LINHAS: > 750
// ===================================================================================

// -----------------------------------------------------------------------------------
// SEÇÃO 1: IMPORTAÇÕES
// Importando hooks do React, componentes de UI (shadcn/ui), biblioteca de gráficos
// (recharts), ícones (lucide-react) e utilitários da aplicação (api, toast).
// -----------------------------------------------------------------------------------
import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import {
  TrendingUp,
  Play,
  RefreshCw,
  AlertCircle,
  Activity,
  BarChart3,
  Pause,
  PlayCircle,
  PauseCircle,
  Clock
} from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

// -----------------------------------------------------------------------------------
// SEÇÃO 2: DEFINIÇÃO DO COMPONENTE
// O componente principal `PredictionView` que recebe `selectedLine`, 
// `selectedTarget` e `selectedModel` como propriedades.
// -----------------------------------------------------------------------------------
const PredictionView = ({ selectedLine, selectedTarget, selectedModel }) => {

  // ---------------------------------------------------------------------------------
  // SEÇÃO 3: ESTADOS (useState)
  // Gerenciamento do estado interno do componente.
  // ---------------------------------------------------------------------------------

  // Armazena o resultado da última predição individual.
  const [prediction, setPrediction] = useState(null)

  // Armazena os dados formatados para exibição no gráfico.
  const [chartData, setChartData] = useState([])

  // Armazena as métricas e o status do modelo selecionado (ex: R² score).
  const [modelStatus, setModelStatus] = useState(null)

  // Controla o estado de "carregando" para uma predição única.
  const [predicting, setPredicting] = useState(false)

  // Controla o estado de "carregando" para o carregamento de dados do gráfico.
  const [loading, setLoading] = useState(false)

  // Flag para ativar ou desativar a atualização automática do gráfico.
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Flag que controla se o processo de predições contínuas está ativo.
  const [continuousPredictions, setContinuousPredictions] = useState(false)

  // Estado que reflete o status de predições contínuas vindo da API.
  const [continuousStatus, setContinuousStatus] = useState(false)


  // Estado para o filtro de data inicial.
  const [startDate, setStartDate] = useState(() => {
    const date = new Date()
    date.setDate(date.getDate() - 7) // Padrão: 7 dias atrás
    return date.toISOString().split('T')[0]
  })

  // Estado para o filtro de data final.
  const [endDate, setEndDate] = useState(() => {
    return new Date().toISOString().split('T')[0]
  })

  // Estado para o filtro de hora inicial.
  const [startTime, setStartTime] = useState('00:00')

  // Estado para o filtro de hora final.
  const [endTime, setEndTime] = useState('23:59')

  // Controla a visibilidade dos campos de filtro de hora.
  const [showTimeFilters, setShowTimeFilters] = useState(false)

  // ---------------------------------------------------------------------------------
  // SEÇÃO 4: HOOKS E REFERÊNCIAS
  // Utilização de hooks como `useToast` e `useRef` para interações e
  // armazenamento de referências a intervalos.
  // ---------------------------------------------------------------------------------

  // Hook para exibir notificações (toasts).
  const { toast } = useToast()

  // --- ADICIONE ESTA FUNÇÃO ---
  // Nova função para carregar a última predição
  const loadLastPrediction = async () => {
    if (!selectedModel) return // Não faz nada se não tiver modelo
    try {
      // 1. Chama a API que busca a última predição salva no banco
      const data = await api.getLastPrediction(selectedModel.id)

      // 2. Atualiza o estado 'prediction', o que vai atualizar o card
      setPrediction(data)
    } catch (error) {
      // É normal falhar se não houver predições (ex: modelo novo)
      // Não precisamos mostrar um erro, apenas limpamos o card.
      console.error('Nenhuma predição anterior encontrada:', error)
      setPrediction(null)
    }
  }
  // --- FIM DA NOVA FUNÇÃO ---

  // Referência para o `setInterval` da atualização automática do gráfico.
  const autoRefreshInterval = useRef(null)

  // Referência para o `setInterval` das predições contínuas.
  const continuousInterval = useRef(null)

  // ---------------------------------------------------------------------------------
  // SEÇÃO 5: EFEITOS COLATERAIS (useEffect)
  // Lógica que roda em resposta a mudanças nas props ou no estado.
  // ---------------------------------------------------------------------------------

  // Efeito para carregar o status do modelo sempre que um novo modelo for selecionado.
  useEffect(() => {
    if (selectedModel) {
      loadModelStatus()
      checkContinuousStatus()
      loadLastPrediction() // <-- ADICIONADO: Carrega a predição ao abrir
    }
  }, [selectedModel])

  // Efeito para recarregar os dados do gráfico sempre que um filtro for alterado.
  useEffect(() => {
    if (selectedTarget) {
      loadChartData()
    }
    if (selectedTarget) {
      loadChartData()
    }
  }, [selectedTarget, startDate, endDate, startTime, endTime])

  // Efeito para gerenciar o `setInterval` de auto-refresh do gráfico.
  // Inicia ou para o intervalo baseado na flag `autoRefresh`.
  useEffect(() => {
    if (autoRefresh && selectedTarget) {
      autoRefreshInterval.current = setInterval(() => {
        loadChartData()
        loadLastPrediction() // <-- ADICIONADO: Atualiza o card junto com o gráfico
      }, 5000)
    } else {


      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current)
        autoRefreshInterval.current = null
      }
    }

    // Função de limpeza para o efeito.
    return () => {
      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current)
      }
    }
  }, [autoRefresh, selectedTarget, selectedModel, startDate, endDate, startTime, endTime])

  // Efeito de limpeza geral, executado quando o componente é desmontado.
  // Garante que todos os intervalos sejam limpos para evitar vazamento de memória.
  useEffect(() => {
    return () => {
      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current)
      }
      if (continuousInterval.current) {
        clearInterval(continuousInterval.current)
      }
    }
  }, []) // Array de dependências vazio significa que só roda ao montar/desmontar.

  // ---------------------------------------------------------------------------------
  // SEÇÃO 6: FUNÇÕES DE LÓGICA E CHAMADAS DE API
  // Funções que buscam dados, manipulam o estado e interagem com a API.
  // ---------------------------------------------------------------------------------

  // Busca o status e as métricas do modelo selecionado na API.
  const loadModelStatus = async () => {
    if (!selectedModel) return

    try {
      const data = await api.getModelStatus(selectedModel.id)
      setModelStatus(data)
    } catch (error) {
      console.error('Erro ao carregar status do modelo:', error)
    }
  }

  // Verifica na API se as predições contínuas já estão ativas para este modelo.
  const checkContinuousStatus = async () => {
    if (!selectedModel) return

    try {
      const response = await api.getContinuousPredictionsStatus(selectedModel.id)
      setContinuousStatus(response.is_running)
      setContinuousPredictions(response.is_running)
    } catch (error) {
      console.error('Erro ao verificar status de predições contínuas:', error)
    }
  }

  // Função para os botões de filtro rápido de dias (1d, 7d, 30d).
  const setQuickDateRange = (days) => {

    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)

    setEndDate(end.toISOString().split('T')[0])
    setStartDate(start.toISOString().split('T')[0])
    setStartTime('00:00')
    setEndTime('23:59')
    setShowTimeFilters(false) // Garante que os filtros de hora fiquem ocultos.
  }

  // Função para os botões de filtro rápido de horas (1h, 6h, 12h).
  const setQuickTimeRange = (hours) => {

    const end = new Date()
    const start = new Date()
    start.setTime(start.getTime() - (hours * 60 * 60 * 1000))

    if (start.toDateString() === end.toDateString()) {
      setStartDate(start.toISOString().split('T')[0])
      setEndDate(end.toISOString().split('T')[0])
      setStartTime(start.toTimeString().slice(0, 5))
      setEndTime(end.toTimeString().slice(0, 5))
    } else {
      setStartDate(start.toISOString().split('T')[0])
      setEndDate(end.toISOString().split('T')[0])
      setStartTime(start.toTimeString().slice(0, 5))
      setEndTime(end.toTimeString().slice(0, 5))
    }
    setShowTimeFilters(true) // Garante que os filtros de hora fiquem visíveis.
  }

  // Função para gerenciar o clique no seletor de data.
  // Função para gerenciar o clique no seletor de data inicial.
  const handleStartDateChange = (e) => {
    setStartDate(e.target.value);
    setShowTimeFilters(true);
  };

  // Função para gerenciar o clique no seletor de data final.
  const handleEndDateChange = (e) => {
    setEndDate(e.target.value);
    setShowTimeFilters(true);
  };

  // ✅ AJUSTE 1: Lógica do Toggle de Auto-Refresh
  // Esta nova função garante que, ao desativar o auto-refresh, uma última
  // busca de dados seja feita para sincronizar o gráfico com os filtros.
  const handleAutoRefreshToggle = (checked) => {
    setAutoRefresh(checked);
    if (!checked) {
      // Se o usuário está desativando, faz uma última atualização.
      loadChartData();
    }
  };

  // Busca os dados históricos (medidos e preditos) para popular o gráfico.
  const loadChartData = async () => {
    if (!selectedTarget) return

    setLoading(true)
    try {
      let startDateTime, endDateTime

      // Modo Histórico: Usa os filtros
      startDateTime = new Date(startDate + 'T' + startTime + ':00')
      endDateTime = new Date(endDate + 'T' + endTime + ':59')

      const data = await api.getData({
        target_id: selectedTarget.id,
        start_time: startDateTime.toISOString(),
        end_time: endDateTime.toISOString(),
        data_type: 'prediction',
        model_id: selectedModel?.id,
        limit: 2000 // Aumentado para melhor visualização
      })

      const transformedData = data
        .map(item => ({
          // ✅ AJUSTE 2: Correção de Fuso Horário (Timezone)
          // Adicionamos 'timeZone' para forçar a conversão do timestamp (que vem em UTC)
          // para o horário local de São Paulo (GMT-3), corrigindo a diferença de 3 horas.
          timestamp: new Date(item.timestamp).toLocaleString('pt-BR', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            timeZone: 'America/Sao_Paulo'
          }),
          measured: item.measured_value,
          predicted: item.predicted_value,
          date: new Date(item.timestamp)
        }))
        .sort((a, b) => a.date - b.date)

      setChartData(transformedData)
    } catch (error) {
      if (autoRefresh) {
        console.error('Erro ao carregar dados do gráfico:', error)
      } else {
        toast({
          title: "Erro",
          description: "Erro ao carregar dados do gráfico",
          variant: "destructive"
        })
      }
    } finally {
      setLoading(false)
    }
  }

  // Executa uma única predição sob demanda.
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

      setTimeout(() => {
        loadChartData()
      }, 1000)
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

  // Ativa ou desativa o modo de predições contínuas.
  // Esta função agora chama a API do backend para iniciar/parar o loop
  const handleToggleContinuousPredictions = async () => {
    if (!selectedModel) {
      toast({
        title: "Erro",
        description: "Selecione um modelo para ativar predições contínuas",
        variant: "destructive"
      })
      return
    }

    // Usa o 'continuousStatus' (que vem da API) como a fonte da verdade
    const isCurrentlyRunning = continuousStatus;

    try {
      if (isCurrentlyRunning) {
        // --- PARAR ---
        await api.stopContinuousPredictions({ model_id: selectedModel.id })
        setContinuousPredictions(false) // Atualiza o estado visual do botão
        setContinuousStatus(false)      // Atualiza o status real

        // Limpa qualquer intervalo local (por segurança, caso exista de versões antigas)
        if (continuousInterval.current) {
          clearInterval(continuousInterval.current)
          continuousInterval.current = null
        }

        toast({
          title: "Predições Paradas",
          description: "O backend foi instruído a parar as predições"
        })
      } else {
        // --- INICIAR ---
        await api.startContinuousPredictions({ model_id: selectedModel.id, interval: 5 })
        setContinuousPredictions(true) // Atualiza o estado visual do botão
        setContinuousStatus(true)      // Atualiza o status real

        loadLastPrediction() // <-- ADICIONADO: Atualiza o card imediatamente

        // Não precisamos mais de setInterval local. O backend está no controle.

        toast({
          title: "Predições Iniciadas",
          description: "O backend está executando predições automaticamente"
        })
      }


    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao configurar predições contínuas",
        variant: "destructive"
      })
      // Desfaz a mudança visual se a API falhar
      setContinuousPredictions(isCurrentlyRunning)
      setContinuousStatus(isCurrentlyRunning)
    }
  }

  // ---------------------------------------------------------------------------------
  // SEÇÃO 7: FUNÇÕES UTILITÁRIAS DE FORMATAÇÃO
  // Pequenas funções para formatar números e datas para exibição na UI.
  // ---------------------------------------------------------------------------------

  // Formata um valor numérico para um número fixo de casas decimais.
  const formatValue = (value, decimals = 4) => {
    if (value === null || value === undefined) return 'N/A'
    return typeof value === 'number' ? value.toFixed(decimals) : value
  }

  // Formata uma string de data para o padrão local (pt-BR).
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    // ✅ AJUSTE 2: Correção de Fuso Horário (Timezone)
    // Aplicando a mesma correção aqui para consistência em toda a UI.
    return new Date(dateString).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })
  }

  // Função específica para formatar os valores dentro do tooltip do gráfico.
  const formatTooltipValue = (value, name) => {
    if (value === null || value === undefined) return ['N/A', name]
    const label = name === 'measured' ? 'Valor Medido' : 'Valor Predito'
    return [formatValue(value), label]
  }

  // ---------------------------------------------------------------------------------
  // SEÇÃO 8: RENDERIZAÇÃO CONDICIONAL (ESTADO VAZIO)
  // Se nenhum target ou modelo for selecionado, exibe uma mensagem instrutiva.
  // ---------------------------------------------------------------------------------
  if (!selectedTarget || !selectedModel) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Visualização de Predições</h1>
          <p className="text-muted-foreground">
            Visualize e execute predições em tempo real
          </p>
        </div>

        <Card>
          <CardContent className="text-center py-12">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Target e Modelo necessários</h3>
            <p className="text-muted-foreground">
              Selecione um target e um modelo na barra de navegação para visualizar predições
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ---------------------------------------------------------------------------------
  // SEÇÃO 9: RENDERIZAÇÃO PRINCIPAL DO COMPONENTE (JSX)
  // Estrutura JSX que compõe a interface do usuário quando há um target e modelo.
  // ---------------------------------------------------------------------------------
  return (
    <div className="space-y-6">
      {/* Bloco do Cabeçalho da Página */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Visualização de Predições</h1>
          <p className="text-muted-foreground">
            Predições para <strong>{selectedTarget.target_name}</strong> usando <strong>{selectedModel.model_name}</strong>
          </p>
        </div>

        {/* Botão Principal de Ação (Iniciar/Parar Predições) */}
        <Button
          onClick={handleToggleContinuousPredictions}
          size="lg"
          className={`flex items-center space-x-3 px-8 py-4 text-lg font-semibold transition-all duration-300 ${continuousPredictions
            ? 'bg-red-600 hover:bg-red-700 dark:bg-red-500 dark:hover:bg-red-600 animate-pulse'
            : 'bg-green-600 hover:bg-green-700 dark:bg-green-500 dark:hover:bg-green-600 hover:scale-105'
            } shadow-lg hover:shadow-xl`}
        >
          {continuousPredictions ? (
            <>
              <Pause className="h-6 w-6 animate-bounce" />
              <span>Parar Predições</span>
            </>
          ) : (
            <>
              <Play className="h-6 w-6 transition-transform duration-300 hover:scale-110" />
              <span>Predizer</span>
            </>
          )}
        </Button>
      </div>

      {/* Grid com os Cards de Status */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Card: Última Predição */}
        <Card className={continuousPredictions ? 'ring-2 ring-green-500 ring-opacity-50' : ''}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Última Predição</CardTitle>
            <TrendingUp className={`h-4 w-4 ${continuousPredictions ? 'text-green-500 animate-pulse' : 'text-muted-foreground'}`} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">
              {prediction ? formatValue(prediction.predicted_value) : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">
              {selectedTarget.target_unit || 'unidade'}
              {prediction?.confidence_std_dev && ` ± ${formatValue(prediction.confidence_std_dev)}`}
            </p>
          </CardContent>
        </Card>

        {/* Card: Precisão do Modelo */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Precisão do Modelo</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {modelStatus?.r2_score ? `${(modelStatus.r2_score * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">
              R² Score
            </p>
          </CardContent>
        </Card>

        {/* Card: Status do Modelo */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Status do Modelo</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              <Badge variant={modelStatus?.status === 'trained' ? 'default' : 'secondary'}>
                {modelStatus?.status === 'trained' ? 'Treinado' : 'Não Treinado'}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {modelStatus?.sample_count || 0} amostras de treino
            </p>
          </CardContent>
        </Card>

        {/* Card: Status das Predições Automáticas */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Predições Automáticas</CardTitle>
            {continuousPredictions ? (
              <Play className="h-4 w-4 text-green-600 animate-pulse" />
            ) : (
              <Pause className="h-4 w-4 text-muted-foreground" />
            )}
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              <Badge variant={continuousPredictions ? 'default' : 'secondary'}>
                {continuousPredictions ? 'Ativo' : 'Inativo'}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {continuousPredictions ? 'Executando a cada 5s' : 'Parado'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Grid de Conteúdo Principal (Gráfico e Detalhes) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Card do Gráfico (Ocupa 2 colunas em telas grandes) */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Histórico de Predições</span>

              {/* Painel de Filtros do Gráfico */}
              <div className="flex items-center space-x-2">

                {/* Botões de Filtro Rápido */}
                <div className="flex items-center space-x-1">
                  {showTimeFilters ? (
                    <>
                      <Button variant="outline" size="sm" onClick={() => setQuickTimeRange(1)} className="text-xs px-2 py-1 h-7">1h</Button>
                      <Button variant="outline" size="sm" onClick={() => setQuickTimeRange(6)} className="text-xs px-2 py-1 h-7">6h</Button>
                      <Button variant="outline" size="sm" onClick={() => setQuickTimeRange(12)} className="text-xs px-2 py-1 h-7">12h</Button>
                    </>
                  ) : (
                    <>
                      <Button variant="outline" size="sm" onClick={() => setQuickDateRange(1)} className="text-xs px-2 py-1 h-7">1d</Button>
                      <Button variant="outline" size="sm" onClick={() => setQuickDateRange(7)} className="text-xs px-2 py-1 h-7">7d</Button>
                      <Button variant="outline" size="sm" onClick={() => setQuickDateRange(30)} className="text-xs px-2 py-1 h-7">30d</Button>
                    </>
                  )}
                </div>

                {/* Filtro de Data e Hora */}
                <div className="flex items-center space-x-2">
                  <Label htmlFor="start-date" className="text-sm whitespace-nowrap">
                    De:
                  </Label>
                  <Input
                    id="start-date"
                    type="date"
                    value={startDate}
                    onChange={handleStartDateChange}
                    className="w-auto text-sm cursor-pointer"
                  />
                  <Label htmlFor="end-date" className="text-sm whitespace-nowrap">
                    Até:
                  </Label>
                  <Input
                    id="end-date"
                    type="date"
                    value={endDate}
                    onChange={handleEndDateChange}
                    className="w-auto text-sm cursor-pointer"
                  />
                  {showTimeFilters && (
                    <>
                      <Input
                        type="time"
                        value={startTime}
                        onChange={(e) => setStartTime(e.target.value)}
                        className="w-auto text-sm"
                      />
                      <Label className="text-sm whitespace-nowrap">até</Label>
                      <Input
                        type="time"
                        value={endTime}
                        onChange={(e) => setEndTime(e.target.value)}
                        className="w-auto text-sm"
                      />
                    </>
                  )}
                </div>

                {/* Botão para alternar a visibilidade do filtro de hora */}
                <Button variant={showTimeFilters ? "default" : "outline"} size="sm" onClick={() => setShowTimeFilters(!showTimeFilters)} className="text-xs px-2 py-1 h-7" title="Filtrar por hora">
                  <Clock className="h-3 w-3" />
                </Button>

                {/* Switch de Auto-Refresh */}
                <div className="flex items-center space-x-2">
                  <Switch id="auto-refresh" checked={autoRefresh} onCheckedChange={handleAutoRefreshToggle} />
                  <Label htmlFor="auto-refresh" className="text-sm">Auto-atualizar</Label>
                </div>

                {/* Botão para forçar a atualização */}
                <Button variant="outline" size="sm" onClick={loadChartData} disabled={loading}>
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
              </div>
            </CardTitle>

            {/* Descrição do Card com o período selecionado */}
            <CardDescription>
              Comparação entre valores medidos e preditos ({new Date(startDate).toLocaleDateString('pt-BR')} {showTimeFilters ? startTime : ''} - {new Date(endDate).toLocaleDateString('pt-BR')} {showTimeFilters ? endTime : ''})
              {autoRefresh && (<span className="text-green-600 ml-2">• Atualizando automaticamente</span>)}
              {continuousPredictions && (<span className="text-green-600 ml-2 animate-pulse">• Predições ativas</span>)}
            </CardDescription>
          </CardHeader>

          {/* Conteúdo do Card do Gráfico */}
          <CardContent>
            {loading && !autoRefresh ? (
              <div className="h-80 flex items-center justify-center">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : chartData.length > 0 ? (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 12 }} label={{ value: selectedTarget.target_unit || 'Valor', angle: -90, position: 'insideLeft' }} />
                    <Tooltip formatter={formatTooltipValue} labelStyle={{ color: '#333' }} />
                    <Legend />
                    <Line type="monotone" dataKey="measured" stroke="#2563eb" strokeWidth={2} dot={{ r: 4 }} name="measured" connectNulls={true} />
                    <Line type="monotone" dataKey="predicted" stroke="#dc2626" strokeWidth={3} strokeDasharray="5 5" dot={{ r: 4 }} name="predicted" connectNulls={true} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-80 flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Nenhum dado disponível</p>
                  <p className="text-sm">Faça algumas predições para ver o gráfico</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Card de Informações Detalhadas do Modelo */}
        <Card>
          <CardHeader>
            <CardTitle>Informações do Modelo</CardTitle>
            <CardDescription>Detalhes sobre o modelo selecionado</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="text-sm font-medium mb-2">Nome do Modelo</div>
              <div className="text-sm text-muted-foreground">{selectedModel.model_name}</div>
            </div>

            <div>
              <div className="text-sm font-medium mb-2">Tipo</div>
              <Badge variant="outline">{selectedModel.model_type}</Badge>
            </div>

            {modelStatus?.trained_at && (
              <div>
                <div className="text-sm font-medium mb-2">Último Treinamento</div>
                <div className="text-sm text-muted-foreground">{formatDate(modelStatus.trained_at)}</div>
              </div>
            )}

            {modelStatus?.r2_score != null && (
              <div>
                <div className="text-sm font-medium mb-2">R² Score</div>
                <div className="space-y-2">
                  <div className="text-sm">{formatValue(modelStatus.r2_score)}</div>
                  <Progress value={Math.max(0, Math.min(100, modelStatus.r2_score * 100))} />
                </div>
              </div>
            )}

            {modelStatus?.mse != null && (
              <div>
                <div className="text-sm font-medium mb-2">MSE</div>
                <div className="text-sm text-muted-foreground">{formatValue(modelStatus.mse)}</div>
              </div>
            )}

            <div>
              <div className="text-sm font-medium mb-2">Amostras de Treino</div>
              <div className="text-sm text-muted-foreground">{modelStatus?.sample_count || 0}</div>
            </div>

            {/* Seção de Importância das Features */}
            {modelStatus?.feature_importances && modelStatus.feature_importances.length > 0 && (
              <div>
                <div className="text-sm font-medium mb-2">Principais Features</div>
                <div className="space-y-2">
                  {modelStatus.feature_importances.slice(0, 5).map(([feature, importance]) => (
                    <div key={feature} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="truncate max-w-32" title={feature}>
                          {feature.length > 20 ? `${feature.substring(0, 20)}...` : feature}
                        </span>
                        <span>{(importance * 100).toFixed(1)}%</span>
                      </div>
                      <Progress value={importance * 100} className="h-1" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Seção da Última Predição (se existir) */}
            {prediction && (
              <div className="pt-4 border-t">
                <div className="text-sm font-medium mb-2">Última Predição</div>
                <div className="space-y-1">
                  <div className="text-lg font-bold text-primary">
                    {formatValue(prediction.predicted_value)} {selectedTarget.target_unit}
                  </div>
                  {prediction.confidence_std_dev && (
                    <div className="text-xs text-muted-foreground">
                      Confiança: ± {formatValue(prediction.confidence_std_dev)}
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground">
                    {formatDate(prediction.timestamp)}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Exportação padrão do componente.
export default PredictionView