import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Zap, TrendingUp } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

export default function Simulation({ selectedLine, selectedTarget, selectedModel }) {
  const [models, setModels] = useState([])
  const [selectedModelId, setSelectedModelId] = useState(null)
  const [metadata, setMetadata] = useState(null)
  const [featureValues, setFeatureValues] = useState({})
  const [prediction, setPrediction] = useState(null)
  const [predictionHistory, setPredictionHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Carregar modelos disponíveis quando target é selecionado
  useEffect(() => {
    if (selectedTarget) {
      fetchModels(selectedTarget.id)
    }
  }, [selectedTarget])

  // Carregar metadados quando modelo é selecionado
  useEffect(() => {
    if (selectedModelId) {
      fetchMetadata(selectedModelId)
    }
  }, [selectedModelId])

  // Fazer predição sempre que os valores das features mudarem
  useEffect(() => {
    if (selectedModelId && Object.keys(featureValues).length > 0) {
      simulatePrediction()
    }
  }, [featureValues, selectedModelId])

  const fetchModels = async (targetId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models?target_id=${targetId}`)
      const data = await response.json()
      // Filtrar apenas modelos treinados
      const trainedModels = data.filter(m => m.trained_at !== null)
      setModels(trainedModels)
      
      if (trainedModels.length > 0) {
        setSelectedModelId(trainedModels[0].id)
      }
    } catch (err) {
      setError('Erro ao carregar modelos: ' + err.message)
    }
  }

  const fetchMetadata = async (modelId) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/models/${modelId}/metadata`)
      if (!response.ok) throw new Error('Erro ao buscar metadados')
      
      const data = await response.json()
      setMetadata(data)
      
      // Inicializar valores das features com a média
      const initialValues = {}
      data.features.forEach(feature => {
        const range = data.feature_ranges[feature]
        initialValues[feature] = range ? range.mean : 50
      })
      setFeatureValues(initialValues)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const simulatePrediction = async () => {
    if (!selectedModelId || Object.keys(featureValues).length === 0) return

    try {
      const response = await fetch(`${API_BASE_URL}/api/models/${selectedModelId}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features: featureValues })
      })
      
      if (!response.ok) throw new Error('Erro na simulação')
      
      const data = await response.json()
      setPrediction(data.predicted_value)
      
      // Adicionar ao histórico (mantém últimos 10)
      setPredictionHistory(prev => {
        const newHistory = [...prev, data.predicted_value].slice(-10)
        return newHistory
      })
    } catch (err) {
      console.error('Erro na simulação:', err)
    }
  }

  const handleFeatureChange = (feature, value) => {
    setFeatureValues(prev => ({
      ...prev,
      [feature]: parseFloat(value)
    }))
  }

  // Preparar dados para o gráfico de Feature Importance
  const importanceData = metadata?.feature_importances?.map(item => ({
    name: item.feature,
    importance: (item.importance * 100).toFixed(1)
  })) || []

  // Cores para o gráfico de importância
  const COLORS = ['#00CED1', '#0EA5E9', '#3B82F6', '#6366F1', '#8B5CF6']

  if (!selectedTarget) {
    return (
      <Alert>
        <AlertDescription>
          Selecione uma Linha e um Target no cabeçalho para começar a simulação.
        </AlertDescription>
      </Alert>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Simulador de Futuro</h1>
          <p className="text-muted-foreground">
            Manipule variáveis de processo e veja o impacto em tempo real
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Seleção de Modelo */}
      <Card>
        <CardHeader>
          <CardTitle>Modelo de Simulação</CardTitle>
          <CardDescription>Selecione o modelo treinado para simular</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={selectedModelId?.toString()} onValueChange={(val) => setSelectedModelId(parseInt(val))}>
            <SelectTrigger>
              <SelectValue placeholder="Selecione um modelo" />
            </SelectTrigger>
            <SelectContent>
              {models.map(model => (
                <SelectItem key={model.id} value={model.id.toString()}>
                  {model.model_name} (R²: {model.r2_score?.toFixed(3)})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {metadata && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Painel de Controle (Esquerda) */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="bg-slate-900 text-white">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5 text-cyan-400" />
                  Controle de Features
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Ajuste as variáveis de processo
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {metadata.features.map(feature => {
                  const range = metadata.feature_ranges[feature]
                  const value = featureValues[feature] || range.mean

                  return (
                    <div key={feature} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label className="text-sm font-medium">{feature}</Label>
                        <Input
                          type="number"
                          value={value.toFixed(2)}
                          onChange={(e) => handleFeatureChange(feature, e.target.value)}
                          className="w-24 h-8 text-right bg-slate-800 border-slate-700"
                          step="0.1"
                        />
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <span>{range.min.toFixed(1)}</span>
                        <Slider
                          value={[value]}
                          onValueChange={([val]) => handleFeatureChange(feature, val)}
                          min={range.min}
                          max={range.max}
                          step={(range.max - range.min) / 100}
                          className="flex-1"
                        />
                        <span>{range.max.toFixed(1)}</span>
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          </div>

          {/* Painel de Resultados (Direita) */}
          <div className="lg:col-span-3 space-y-4">
            {/* Gauge de Predição */}
            <Card>
              <CardHeader>
                <CardTitle>Predição Estimada</CardTitle>
                <CardDescription>{selectedTarget.target_name}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center py-8">
                  <div className="text-center">
                    <div className="text-6xl font-bold text-cyan-600">
                      {prediction !== null ? prediction.toFixed(2) : '--'}
                    </div>
                    <div className="text-lg text-muted-foreground mt-2">
                      {selectedTarget.target_unit || 'unidade'}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Gráfico de Feature Importance */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Feature Importance
                </CardTitle>
                <CardDescription>
                  Impacto de cada variável no resultado
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={importanceData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="name" type="category" width={150} />
                    <Tooltip />
                    <Bar dataKey="importance" fill="#00CED1">
                      {importanceData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
