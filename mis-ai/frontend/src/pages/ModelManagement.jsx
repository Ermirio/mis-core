import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Brain,
  Plus,
  Play,
  Settings,
  ChevronDown,
  AlertCircle,
  TrendingUp,
  Edit,
  Trash2,
  MoreVertical,
  ToggleLeft,
  ToggleRight
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

const ModelManagement = ({ selectedTarget, setSelectedModel, onDataChange }) => {
  const [models, setModels] = useState([])
  const [loading, setLoading] = useState(false)
  const [training, setTraining] = useState({})
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingModel, setEditingModel] = useState(null)
  const [formData, setFormData] = useState({
    model_name: '',
    model_type: 'RandomForest',
    parameters: {
      n_estimators: 100,
      max_depth: 10,
      random_state: 42
    }
  })
  const { toast } = useToast()

  useEffect(() => {
    if (selectedTarget) {
      loadModels()
    } else {
      setModels([])
    }
  }, [selectedTarget])

  const loadModels = async () => {
    try {
      const data = await api.getModels(selectedTarget.id)
      setModels(data ?? [])

      // Carregar status de cada modelo
      for (const model of data ?? []) {
        loadModelStatus(model.id)
      }
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro ao carregar modelos",
        variant: "destructive"
      })
    }
  }

  const loadModelStatus = async (modelId) => {
    try {
      const status = await api.getModelStatus(modelId)
      setModels(prev => prev.map(model =>
        model.id === modelId ? { ...model, status } : model
      ))
    } catch (error) {
      console.error(`Erro ao carregar status do modelo ${modelId}:`, error)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.model_name.trim()) {
      toast({
        title: "Erro",
        description: "Nome do modelo é obrigatório",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      await api.createModel({
        target_id: selectedTarget.id,
        model_name: formData.model_name,
        model_type: formData.model_type,
        parameters: formData.parameters,
        is_active: true
      })
      toast({
        title: "Sucesso",
        description: "Modelo criado com sucesso"
      })
      setDialogOpen(false)
      resetForm()
      loadModels()
      if (onDataChange) onDataChange()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao criar modelo",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!formData.model_name.trim()) {
      toast({
        title: "Erro",
        description: "Nome do modelo é obrigatório",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      await api.updateModel(editingModel.id, {
        model_name: formData.model_name,
        model_type: formData.model_type,
        parameters: formData.parameters
      })
      toast({
        title: "Sucesso",
        description: "Modelo atualizado com sucesso"
      })
      setEditDialogOpen(false)
      setEditingModel(null)
      resetForm()
      loadModels()
      if (onDataChange) onDataChange()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao atualizar modelo",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (model) => {
    setEditingModel(model)
    setFormData({
      model_name: model.model_name,
      model_type: model.model_type,
      parameters: model.model_parameters || {
        n_estimators: 100,
        max_depth: 10,
        random_state: 42
      }
    })
    setEditDialogOpen(true)
  }

  const handleDelete = async (modelId) => {
    try {
      await api.deleteModel(modelId)
      toast({
        title: "Sucesso",
        description: "Modelo excluído com sucesso"
      })
      loadModels()
      if (onDataChange) onDataChange()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao excluir modelo",
        variant: "destructive"
      })
    }
  }

  const handleToggleActive = async (modelId, isActive) => {
    try {
      await api.updateModel(modelId, { is_active: !isActive })
      toast({
        title: "Sucesso",
        description: `Modelo ${!isActive ? 'ativado' : 'desativado'} com sucesso`
      })
      loadModels()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao atualizar status do modelo",
        variant: "destructive"
      })
    }
  }

  const handleTrain = async (modelId) => {
    setTraining(prev => ({ ...prev, [modelId]: true }))
    try {
      await api.trainModel(modelId)
      toast({
        title: "Sucesso",
        description: "Modelo treinado com sucesso"
      })
      loadModelStatus(modelId)
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao treinar modelo",
        variant: "destructive"
      })
    } finally {
      setTraining(prev => ({ ...prev, [modelId]: false }))
    }
  }

  const handleSelectModel = (model) => {
    // CORREÇÃO: Só seleciona se estiver ativo (igual ao TargetManagement)
    if (model.is_active) {
      setSelectedModel(model)
      toast({
        title: "Modelo Selecionado",
        description: `${model.model_name} foi selecionado como modelo ativo`
      })
    } else {
      toast({
        title: "Aviso",
        description: `O modelo "${model.model_name}" está inativo e não pode ser selecionado.`,
        variant: "default"
      })
    }
  }

  const resetForm = () => {
    setFormData({
      model_name: '',
      model_type: 'RandomForest',
      parameters: {
        n_estimators: 100,
        max_depth: 10,
        random_state: 42
      }
    })
  }

  const handleParameterChange = (param, value) => {
    setFormData(prev => ({
      ...prev,
      parameters: {
        ...prev.parameters,
        [param]: value
      }
    }))
  }

  const getParameterFields = () => {
    switch (formData.model_type) {
      case 'RandomForest':
        return (
          <>
            <div>
              <Label htmlFor="n_estimators">Número de Árvores</Label>
              <Input
                id="n_estimators"
                type="number"
                value={formData.parameters.n_estimators}
                onChange={(e) => handleParameterChange('n_estimators', parseInt(e.target.value))}
                min="1"
                max="1000"
              />
            </div>
            <div>
              <Label htmlFor="max_depth">Profundidade Máxima</Label>
              <Input
                id="max_depth"
                type="number"
                value={formData.parameters.max_depth}
                onChange={(e) => handleParameterChange('max_depth', parseInt(e.target.value))}
                min="1"
                max="50"
              />
            </div>
            <div>
              <Label htmlFor="random_state">Seed Aleatória</Label>
              <Input
                id="random_state"
                type="number"
                value={formData.parameters.random_state}
                onChange={(e) => handleParameterChange('random_state', parseInt(e.target.value))}
              />
            </div>
          </>
        )
      case 'LinearRegression':
        return (
          <div className="text-sm text-muted-foreground">
            Regressão Linear não possui parâmetros configuráveis
          </div>
        )
      default:
        return null
    }
  }

  const formatValue = (value, decimals = 4) => {
    if (value === null || value === undefined) return 'N/A'
    return typeof value === 'number' ? value.toFixed(decimals) : value
  }

  if (!selectedTarget) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Gerenciamento de Modelos</h1>
          <p className="text-muted-foreground">
            Gerencie os modelos de predição para cada target
          </p>
        </div>

        <Card>
          <CardContent className="text-center py-12">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhum target selecionado</h3>
            <p className="text-muted-foreground">
              Selecione um target na barra de navegação para gerenciar seus modelos
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
          <h1 className="text-3xl font-bold">Gerenciamento de Modelos</h1>
          <p className="text-muted-foreground">
            Modelos para o target <strong>{selectedTarget.target_name}</strong>
          </p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="flex items-center space-x-2 bg-blue-600 text-white hover:bg-blue-700">
              <Plus className="h-4 w-4" />
              <span>Novo Modelo</span>
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Criar Novo Modelo</DialogTitle>
              <DialogDescription>
                Adicione um novo modelo para o target {selectedTarget.target_name}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="model_name">Nome do Modelo *</Label>
                  <Input
                    id="model_name"
                    value={formData.model_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, model_name: e.target.value }))}
                    placeholder="Ex: RandomForest_v1, Modelo_Otimizado..."
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="model_type">Tipo do Modelo</Label>
                  <Select
                    value={formData.model_type}
                    onValueChange={(value) => setFormData(prev => ({ ...prev, model_type: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="RandomForest">Random Forest</SelectItem>
                      <SelectItem value="LinearRegression">Regressão Linear</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Collapsible>
                  <CollapsibleTrigger asChild>
                    <Button variant="outline" type="button" className="w-full">
                      <Settings className="h-4 w-4 mr-2" />
                      Parâmetros do Modelo
                      <ChevronDown className="h-4 w-4 ml-auto" />
                    </Button>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="space-y-4 mt-4">
                    {getParameterFields()}
                  </CollapsibleContent>
                </Collapsible>
              </div>
              <DialogFooter className="mt-6">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDialogOpen(false)}
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  disabled={loading}
                  className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
                >
                  {loading ? 'Criando...' : 'Criar Modelo'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Editar Modelo</DialogTitle>
            <DialogDescription>
              Edite as configurações do modelo {editingModel?.model_name}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEditSubmit}>
            <div className="space-y-4">
              <div>
                <Label htmlFor="edit_model_name">Nome do Modelo *</Label>
                <Input
                  id="edit_model_name"
                  value={formData.model_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, model_name: e.target.value }))}
                  placeholder="Ex: RandomForest_v1, Modelo_Otimizado..."
                  required
                />
              </div>

              <div>
                <Label htmlFor="edit_model_type">Tipo do Modelo</Label>
                <Select
                  value={formData.model_type}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, model_type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="RandomForest">Random Forest</SelectItem>
                    <SelectItem value="LinearRegression">Regressão Linear</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button variant="outline" type="button" className="w-full">
                    <Settings className="h-4 w-4 mr-2" />
                    Parâmetros do Modelo
                    <ChevronDown className="h-4 w-4 ml-auto" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-4 mt-4">
                  {getParameterFields()}
                </CollapsibleContent>
              </Collapsible>
            </div>
            <DialogFooter className="mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditDialogOpen(false)
                  setEditingModel(null)
                  resetForm()
                }}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={loading}
                className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
              >
                {loading ? 'Salvando...' : 'Salvar Alterações'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Models Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {models.map((model) => (
          <Card
            key={model.id}
            className={`transition-all hover:shadow-lg ${!model.is_active ? 'opacity-50 bg-muted/50' : ''}`}
          >
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center space-x-2 cursor-pointer" onClick={() => handleSelectModel(model)}>
                  <Brain className="h-5 w-5 text-primary" />
                  <span>{model.model_name}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge variant={model.is_active ? 'default' : 'secondary'}>
                    {model.is_active ? 'Ativo' : 'Inativo'}
                  </Badge>
                  <Badge variant={model.status?.status === 'trained' ? 'default' : 'secondary'}>
                    {model.status?.status === 'trained' ? 'Treinado' : 'Não Treinado'}
                  </Badge>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleEdit(model)}>
                        <Edit className="h-4 w-4 mr-2" />
                        Editar
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleToggleActive(model.id, model.is_active)}>
                        {model.is_active ? (
                          <>
                            <ToggleLeft className="h-4 w-4 mr-2" />
                            Desativar
                          </>
                        ) : (
                          <>
                            <ToggleRight className="h-4 w-4 mr-2" />
                            Ativar
                          </>
                        )}
                      </DropdownMenuItem>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onSelect={(e) => e.preventDefault()}
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Excluir
                          </DropdownMenuItem>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Confirmar Exclusão</AlertDialogTitle>
                            <AlertDialogDescription>
                              Tem certeza que deseja excluir permanentemente o modelo "{model.model_name}"?
                              Esta ação é irreversível.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancelar</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDelete(model.id)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              Excluir Permanentemente
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

              </CardTitle>
              <CardDescription>
                {model.model_type} • {model.status?.sample_count || 0} amostras
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Performance Metrics */}
                {model.status?.r2_score != null && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>R² Score:</span>
                      <span className="font-medium">{formatValue(model.status?.r2_score)}</span>
                    </div>
                    <Progress value={Math.max(0, Math.min(100, (model.status?.r2_score ?? 0) * 100))} />
                  </div>
                )}

                {model.status?.mse != null && (
                  <div className="flex items-center justify-between text-sm">
                    <span>MSE:</span>
                    <span className="font-medium">{formatValue(model.status?.mse)}</span>
                  </div>
                )}

                {model.status?.trained_at && (
                  <div className="text-xs text-muted-foreground">
                    Treinado em: {new Date(model.status.trained_at).toLocaleString('pt-BR')}
                  </div>
                )}

                {/* Feature Importances */}
                {model.status?.feature_importances && model.status.feature_importances.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium flex items-center">
                      <TrendingUp className="h-4 w-4 mr-2" />
                      Top Features
                    </div>
                    <div className="space-y-1">
                      {model.status.feature_importances.slice(0, 3).map(([feature, importance]) => (
                        <div key={feature} className="flex items-center justify-between text-xs">
                          <span className="truncate max-w-32" title={feature}>
                            {feature.length > 20 ? `${feature.substring(0, 20)}...` : feature}
                          </span>
                          <span>{(importance * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex space-x-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleTrain(model.id)
                    }}
                    disabled={training[model.id]}
                  >
                    <Play className="h-4 w-4 mr-2" />
                    {training[model.id] ? 'Treinando...' : 'Treinar'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {
        models.length === 0 && (
          <Card>
            <CardContent className="text-center py-12">
              <Brain className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-semibold mb-2">Nenhum modelo encontrado</h3>
              <p className="text-muted-foreground mb-4">
                Comece criando seu primeiro modelo para o target {selectedTarget.target_name}
              </p>
              <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600">
                    <Plus className="h-4 w-4 mr-2" />
                    Criar Primeiro Modelo
                  </Button>
                </DialogTrigger>
              </Dialog>
            </CardContent>
          </Card>
        )
      }
    </div >
  )
}

export default ModelManagement