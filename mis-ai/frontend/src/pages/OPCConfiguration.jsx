import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
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
  Settings,
  Plus,
  Play,
  Square,
  Activity,
  AlertCircle,
  CheckCircle,
  Trash2,
  Edit
} from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'



const getBadgeColor = (category) => {
  switch (category) {
    case 'read': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300 border-blue-200 dark:border-blue-800'
    case 'write': return 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300 border-red-200 dark:border-red-800'
    case 'control': return 'bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-300 border-orange-200 dark:border-orange-800'
    case 'reference': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800'
    case 'target': return 'bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300 border-purple-200 dark:border-purple-800'
    default: return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-700'
  }
}

const getBadgeLabel = (category) => {
  switch (category) {
    case 'read': return '📥 Leitura (Input)'
    case 'write': return '📤 Escrita (Output)'
    case 'control': return '🟠 Controle'
    case 'reference': return '🟡 Referência'
    case 'target': return '🟣 Target (Setpoint)'
    default: return category
  }
}


const ConnectionSection = ({ opcConfig, setOpcConfig }) => {
  const [connectionLoading, setConnectionLoading] = useState(false)
  const { toast } = useToast()

  const handleUpdateConfig = async (e) => {
    e.preventDefault()
    setConnectionLoading(true)
    try {
      const result = await api.updateOPCConfig(opcConfig.opc_url)
      setOpcConfig(prev => ({ ...prev, ...result.config }))
      toast({
        title: result.connected ? "Conectado" : "Salvo (Sem Conexão)",
        description: result.message,
        variant: result.connected ? "default" : "warning"
      })
    } catch (error) {
      toast({
        title: "Erro de Conexão",
        description: error.message || "Falha ao atualizar configuração OPC",
        variant: "destructive"
      })
    } finally {
      setConnectionLoading(false)
    }
  }

  return (
    <Card className="mb-6 border-blue-200 dark:border-blue-900 bg-blue-50/30 dark:bg-blue-950/10">
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Activity className="h-5 w-5 text-blue-600" />
          <span>Conexão com Servidor OPC UA</span>
        </CardTitle>
        <CardDescription>Configuração global do servidor OPC (afeta todas as linhas)</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleUpdateConfig} className="flex gap-4 items-end">
          <div className="flex-1 space-y-2">
            <Label htmlFor="opc-url">URL do Servidor</Label>
            <Input
              id="opc-url"
              value={opcConfig.opc_url || ''}
              onChange={(e) => setOpcConfig({ ...opcConfig, opc_url: e.target.value })}
              placeholder="opc.tcp://192.168.1.10:4840"
              className="bg-background"
            />
          </div>
          <Button type="submit" disabled={connectionLoading}>
            {connectionLoading ? (
              <span className="flex items-center"><Activity className="mr-2 h-4 w-4 animate-spin" /> Conectando...</span>
            ) : (
              <span className="flex items-center"><Settings className="mr-2 h-4 w-4" /> Atualizar & Reconectar</span>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

const OPCConfiguration = ({ selectedLine, selectedTarget, selectedModel }) => {
  const [variables, setVariables] = useState([])
  const [modelVariables, setModelVariables] = useState([]) // [NOVO] Variáveis do modelo selecionado
  const [loggingStatus, setLoggingStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingVariable, setEditingVariable] = useState(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [variableToDelete, setVariableToDelete] = useState(null)
  const [formData, setFormData] = useState({
    node_id: '',
    variable_name: '',
    type: 'Float',
    type_category: 'read',
    description: '',
    target_id: null,
    control_config: {
      control_logic: 'direct',
      relation_factor: 1.0,
      min_adjustment: null,
      max_adjustment: null
    }
  })
  const [targets, setTargets] = useState([])
  const { toast } = useToast()

  // Estado para role no formulário
  // const [modelRole, setModelRole] = useState('') // Removido em favor da inferência automática

  // --- NOVO: Carregar Configuração Global ---
  const [opcConfig, setOpcConfig] = useState({ opc_url: '', is_active: false })
  const [connectionLoading, setConnectionLoading] = useState(false)

  useEffect(() => {
    loadGlobalConfig()
    if (selectedLine) {
      loadTargets()
    }
  }, [])

  useEffect(() => {
    if (selectedLine) {
      loadTargets()
    }
  }, [selectedLine])

  const loadTargets = async () => {
    if (!selectedLine) return
    try {
      const data = await api.getTargets(selectedLine)
      setTargets(data || [])
    } catch (error) {
      console.error("Erro ao carregar targets:", error)
    }
  }

  const loadGlobalConfig = async () => {
    try {
      const data = await api.getOPCConfig()
      if (data) setOpcConfig(data)
    } catch (error) {
      console.error("Erro ao carregar config OPC:", error)
    }
  }

  // Load variables when line or model changes
  useEffect(() => {
    if (selectedLine) {
      loadVariables()
      loadLoggingStatus()
    }
  }, [selectedLine, selectedModel])

  const loadVariables = async () => {
    if (!selectedLine) return
    setLoading(true)
    try {
      const data = await api.getOPCVariables(selectedLine)
      setVariables(data || [])

      // [NOVO] Carregar variáveis do modelo se houver modelo selecionado
      if (selectedModel) {
        // Garantir que temos o ID do modelo
        const modelId = typeof selectedModel === 'object' ? selectedModel.id : selectedModel;
        const mvData = await api.getModelVariables(modelId)
        setModelVariables(mvData || [])
      } else {
        setModelVariables([])
      }
    } catch (error) {
      console.error("Erro ao carregar variáveis:", error)
      toast({
        title: "Erro",
        description: "Falha ao carregar variáveis OPC",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const loadLoggingStatus = async () => {
    if (!selectedLine) return
    try {
      const data = await api.getOPCLoggingStatus(selectedLine)
      setLoggingStatus(data)
    } catch (error) {
      console.error("Erro ao carregar status de logging:", error)
    }
  }

  const handleOpenChange = (open) => {
    setDialogOpen(open)
    if (!open) {
      setEditingVariable(null)
      setFormData({
        node_id: '',
        variable_name: '',
        type: 'Float',
        type_category: 'read',
        description: '',
        target_id: null,
        control_config: {
          control_logic: 'direct',
          relation_factor: 1.0,
          min_adjustment: null,
          max_adjustment: null
        }
      })
      // setModelRole('') // [NOVO] Resetar role removed
    }
  }

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      // Preparar payload baseado no tipo de variável
      const payload = {
        ...formData,
        line: selectedLine,
        // Fix: Incluir target_id para tipo 'target' também
        target_id: (formData.type_category === 'reference' || formData.type_category === 'control' || formData.type_category === 'target') ? formData.target_id : null,
        control_config: formData.type_category === 'control' ? formData.control_config : null
      }

      let savedVariableId = null;

      if (editingVariable) {
        await api.updateOPCVariable(editingVariable.id, payload)
        savedVariableId = editingVariable.id
        toast({ title: "Sucesso", description: "Variável atualizada" })
      } else {
        const newVar = await api.createOPCVariable(payload)
        savedVariableId = newVar.id
        toast({ title: "Sucesso", description: "Variável criada" })
      }

      // [NOVO] ASSOCIAÇÃO AUTOMÁTICA AO MODELO
      if (selectedModel && savedVariableId) {
        // Garantir que temos o ID do modelo (se for objeto ou string)
        const modelId = typeof selectedModel === 'object' ? selectedModel.id : selectedModel;

        // Inferir Role baseado na categoria
        let autoRole = null;
        switch (formData.type_category) {
          case 'read': autoRole = 'input'; break;
          case 'write': autoRole = 'write'; break;
          case 'control': autoRole = 'control'; break;
          case 'reference': autoRole = 'reference'; break;
          case 'target': autoRole = 'write'; break; // Target é um output do modelo (setpoint)
          default: autoRole = null;
        }

        if (autoRole) {
          const existingAssoc = modelVariables.find(mv => mv.opc_variable_id === savedVariableId)
          if (existingAssoc) {
            if (existingAssoc.role !== autoRole) {
              await api.updateModelVariable(modelId, existingAssoc.id, { role: autoRole })
            }
          } else {
            await api.addModelVariable(modelId, {
              opc_variable_id: savedVariableId,
              role: autoRole,
              control_config: formData.type_category === 'control' ? formData.control_config : null
            })
          }
        }
      }

      setDialogOpen(false)
      setEditingVariable(null)
      setFormData({
        node_id: '',
        variable_name: '',
        type: 'Float',
        type_category: 'read',
        description: '',
        target_id: null,
        control_config: {
          control_logic: 'direct',
          relation_factor: 1.0,
          min_adjustment: null,
          max_adjustment: null
        }
      })
      // setModelRole('') // Removido
      loadVariables()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Falha ao salvar variável",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (variable) => {
    setEditingVariable(variable)
    setFormData({
      node_id: variable.node_id,
      variable_name: variable.variable_name,
      type: variable.type,
      type_category: variable.type_category || 'read',
      description: variable.description || '',
      target_id: variable.target_id || null,
      control_config: variable.control_config || {
        control_logic: 'direct',
        relation_factor: 1.0,
        min_adjustment: null,
        max_adjustment: null
      }
    })
    setDialogOpen(true)

    // [NOVO] Carregar role do modelo (Não precisa mais setar estado, pois é inferido)
    // if (selectedModel) {
    //   const assoc = modelVariables.find(mv => mv.opc_variable_id === variable.id)
    //   setModelRole(assoc ? assoc.role : '')
    // }
  }

  const handleDeleteClick = (variable) => {
    setVariableToDelete(variable)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!variableToDelete) return
    setLoading(true)
    try {
      if (selectedModel) {
        // [NOVO] Lógica de Dissociação (Remover do Modelo)
        const modelId = typeof selectedModel === 'object' ? selectedModel.id : selectedModel;
        const association = modelVariables.find(mv => mv.opc_variable_id === variableToDelete.id)

        if (association) {
          await api.deleteModelVariable(modelId, association.id)
          toast({ title: "Sucesso", description: "Variável removida do modelo (mantida na linha)" })
        } else {
          throw new Error("Associação não encontrada para este modelo")
        }
      } else {
        // Lógica Original (Exclusão Global)
        await api.deleteOPCVariable(variableToDelete.id)
        toast({ title: "Sucesso", description: "Variável excluída definitivamente" })
      }

      setDeleteDialogOpen(false)
      setVariableToDelete(null)
      loadVariables()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Falha ao excluir variável",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleLogging = async (action) => {
    setLoading(true)
    try {
      if (action === 'start') {
        await api.startOPCLogging(selectedLine)
        toast({ title: "Sucesso", description: "Logging iniciado" })
      } else {
        await api.stopOPCLogging(selectedLine)
        toast({ title: "Sucesso", description: "Logging parado" })
      }
      loadLoggingStatus()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Falha ao controlar logging",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }


  if (!selectedLine) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Configuração OPC</h1>
          <p className="text-muted-foreground">
            Configure o servidor OPC UA e as variáveis de coleta.
          </p>
        </div>

        {/* Exibir configuração global mesmo sem linha selecionada */}
        <ConnectionSection opcConfig={opcConfig} setOpcConfig={setOpcConfig} />

        <Card>
          <CardContent className="text-center py-12">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhuma linha selecionada</h3>
            <p className="text-muted-foreground">
              Selecione uma linha na barra de navegação para configurar variáveis específicas.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Connection Settings (Global) */}
      <ConnectionSection opcConfig={opcConfig} setOpcConfig={setOpcConfig} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Configuração OPC</h1>
          <p className="text-muted-foreground">
            Configurações para <strong>{selectedLine}</strong>
          </p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={handleOpenChange}>
          <DialogTrigger asChild>
            <Button className="flex items-center space-x-2 bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-all duration-200 hover:scale-105 hover:shadow-lg">
              <Plus className="h-4 w-4 transition-transform duration-200 hover:rotate-90" />
              <span>Nova Variável (+)</span>
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingVariable ? 'Editar Variável OPC' : 'Registrar Variável OPC'}
              </DialogTitle>
              <DialogDescription>
                {editingVariable
                  ? `Edite a variável OPC para a linha ${selectedLine}`
                  : `Adicione uma nova variável OPC para a linha ${selectedLine}`
                }
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="node_id">Node ID *</Label>
                  <Input
                    id="node_id"
                    value={formData.node_id}
                    onChange={(e) => handleInputChange('node_id', e.target.value)}
                    placeholder="Ex: ns=2;i=1001"
                    required
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Identificador único do nó OPC
                  </p>
                </div>

                {/* [REMOVIDO] Seletor de Role do Modelo (Agora automático) */}

                <div>
                  <Label htmlFor="variable_name">Nome da Variável *</Label>
                  <Input
                    id="variable_name"
                    value={formData.variable_name}
                    onChange={(e) => handleInputChange('variable_name', e.target.value)}
                    placeholder="Ex: Temperatura, Pressão, Vazão..."
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="type_category">Categoria da Variável</Label>
                  <Select
                    value={formData.type_category}
                    onValueChange={(value) => handleInputChange('type_category', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="read">🔵 Leitura (Input)</SelectItem>
                      <SelectItem value="write">🔴 Escrita (Output)</SelectItem>
                      <SelectItem value="reference">🟡 Referência (Treinamento Auto)</SelectItem>
                      <SelectItem value="control">🟠 Controle (Ajuste Preditivo)</SelectItem>
                      <SelectItem value="target">🟣 Target (Setpoint Dinâmico)</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formData.type_category === 'read' && 'Variável para leitura de dados (sensores, medições)'}
                    {formData.type_category === 'write' && 'Variável para escrita de predições (targets, setpoints)'}
                    {formData.type_category === 'reference' && 'Variável de referência - captura automática de valores medidos para treinamento contínuo'}
                    {formData.type_category === 'control' && 'Variável de controle - recebe recomendações de ajuste baseadas em predições'}
                  </p>
                </div>
                <div>
                  <Label htmlFor="type">Tipo de Dados</Label>
                  <Select
                    value={formData.type}
                    onValueChange={(value) => handleInputChange('type', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Float">Float</SelectItem>
                      <SelectItem value="Integer">Integer</SelectItem>
                      <SelectItem value="Boolean">Boolean</SelectItem>
                      <SelectItem value="String">String</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Campo condicional para variável REFERENCE */}
                {formData.type_category === 'reference' && (
                  <div className="p-4 border-2 border-yellow-300 dark:border-yellow-700 rounded-lg bg-yellow-50 dark:bg-yellow-950/20">
                    <Label htmlFor="target_id" className="flex items-center space-x-2 mb-2">
                      <span className="text-yellow-700 dark:text-yellow-400 font-semibold">🟡 Configuração de Referência</span>
                    </Label>
                    <Select
                      value={formData.target_id?.toString() || ''}
                      onValueChange={(value) => handleInputChange('target_id', parseInt(value))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selecione o Target associado" />
                      </SelectTrigger>
                      <SelectContent>
                        {targets.map(target => (
                          <SelectItem key={target.id} value={target.id.toString()}>
                            {target.target_name} ({target.target_unit})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-yellow-700 dark:text-yellow-400 mt-2">
                      Esta variável capturará automaticamente valores medidos e associará aos dados de treinamento do target selecionado.
                    </p>
                  </div>
                )}

                {/* Campo condicional para variável TARGET */}
                {formData.type_category === 'target' && (
                  <div className="p-4 border-2 border-purple-300 dark:border-purple-700 rounded-lg bg-purple-50 dark:bg-purple-950/20">
                    <Label htmlFor="target_target_id" className="flex items-center space-x-2 mb-2">
                      <span className="text-purple-700 dark:text-purple-400 font-semibold">🟣 Configuração de Setpoint Dinâmico</span>
                    </Label>
                    <Select
                      value={formData.target_id?.toString() || ''}
                      onValueChange={(value) => handleInputChange('target_id', parseInt(value))}
                    >
                      <SelectTrigger id="target_target_id">
                        <SelectValue placeholder="Selecione qual Target esta variável controla" />
                      </SelectTrigger>
                      <SelectContent>
                        {targets.map(target => (
                          <SelectItem key={target.id} value={target.id.toString()}>
                            {target.target_name} ({target.target_unit})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-purple-700 dark:text-purple-400 mt-2">
                      O valor lido desta variável OPC será usado como <strong>Setpoint</strong> (Meta) para o Target selecionado.
                    </p>
                  </div>
                )}

                {/* Campos condicionais para variável CONTROL */}
                {formData.type_category === 'control' && (
                  <div className="p-4 border-2 border-orange-300 dark:border-orange-700 rounded-lg bg-orange-50 dark:bg-orange-950/20 space-y-4">
                    <Label className="flex items-center space-x-2 mb-2">
                      <span className="text-orange-700 dark:text-orange-400 font-semibold">🟠 Configuração de Controle Preditivo</span>
                    </Label>

                    <div className="bg-white dark:bg-black/20 p-3 rounded-md mb-3 border border-orange-200 dark:border-orange-800">
                      <Label htmlFor="control_target" className="mb-2 block">Target ALvo (Obrigatório)</Label>
                      <Select
                        value={formData.target_id?.toString() || ''}
                        onValueChange={(value) => handleInputChange('target_id', parseInt(value))}
                      >
                        <SelectTrigger id="control_target">
                          <SelectValue placeholder="Selecione o Target que esta variável controla" />
                        </SelectTrigger>
                        <SelectContent>
                          {targets.map(target => (
                            <SelectItem key={target.id} value={target.id.toString()}>
                              {target.target_name} ({target.target_unit})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground mt-1">
                        A variável de controle ajustará o processo para atingir o valor ideal deste target.
                      </p>
                    </div>

                    <div>
                      <Label htmlFor="control_logic">Lógica de Controle</Label>
                      <Select
                        value={formData.control_config.control_logic}
                        onValueChange={(value) => handleInputChange('control_config', { ...formData.control_config, control_logic: value })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="direct">⬆️ Direta (erro+ → aumenta controle)</SelectItem>
                          <SelectItem value="reverse">⬇️ Reversa (erro+ → diminui controle)</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-orange-700 dark:text-orange-400 mt-1">
                        {formData.control_config.control_logic === 'direct'
                          ? 'Ex: Temperatura - aumentar aquecimento quando temperatura está baixa'
                          : 'Ex: Velocidade - diminuir velocidade quando peso está alto'}
                      </p>
                    </div>

                    <div>
                      <Label htmlFor="relation_factor">Fator de Relação (0-100%)</Label>
                      <div className="flex items-center space-x-3">
                        <Input
                          id="relation_factor"
                          type="number"
                          min="0"
                          max="1"
                          step="0.01"
                          value={formData.control_config.relation_factor}
                          onChange={(e) => handleInputChange('control_config', { ...formData.control_config, relation_factor: parseFloat(e.target.value) })}
                          className="flex-1"
                        />
                        <span className="text-sm font-mono bg-orange-200 dark:bg-orange-900 px-3 py-2 rounded">
                          {(formData.control_config.relation_factor * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-xs text-orange-700 dark:text-orange-400 mt-1">
                        Controla a intensidade do ajuste. 1.0 = 100% (ajuste total), 0.5 = 50% (ajuste moderado)
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label htmlFor="min_adjustment">Ajuste Mínimo</Label>
                        <Input
                          id="min_adjustment"
                          type="number"
                          step="0.01"
                          value={formData.control_config.min_adjustment || ''}
                          onChange={(e) => handleInputChange('control_config', { ...formData.control_config, min_adjustment: e.target.value ? parseFloat(e.target.value) : null })}
                          placeholder="Opcional"
                        />
                      </div>
                      <div>
                        <Label htmlFor="max_adjustment">Ajuste Máximo</Label>
                        <Input
                          id="max_adjustment"
                          type="number"
                          step="0.01"
                          value={formData.control_config.max_adjustment || ''}
                          onChange={(e) => handleInputChange('control_config', { ...formData.control_config, max_adjustment: e.target.value ? parseFloat(e.target.value) : null })}
                          placeholder="Opcional"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-orange-700 dark:text-orange-400">
                      Limites de segurança para o ajuste sugerido (deixe em branco para sem limite)
                    </p>
                  </div>
                )}

                <div>
                  <Label htmlFor="description">Descrição</Label>
                  <Textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    placeholder="Descrição opcional da variável..."
                    rows={3}
                  />
                </div>
              </div>
              <DialogFooter className="mt-6">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDialogOpen(false)}
                >
                  Cancelar
                </Button>
                <Button type="submit" disabled={loading} className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-all duration-200 hover:scale-105">
                  {loading
                    ? (editingVariable ? 'Atualizando...' : 'Registrando...')
                    : (editingVariable ? 'Atualizar Variável' : 'Registrar Variável')
                  }
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Logging Control */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Activity className="h-5 w-5" />
              <span>Controle de Logging</span>
            </div>
            <Badge
              variant={loggingStatus?.is_logging_active ? 'default' : 'secondary'}
              className="flex items-center space-x-1"
            >
              {loggingStatus?.is_logging_active ? (
                <CheckCircle className="h-3 w-3" />
              ) : (
                <AlertCircle className="h-3 w-3" />
              )}
              <span>{loggingStatus?.is_logging_active ? 'Ativo' : 'Inativo'}</span>
            </Badge>
          </CardTitle>
          <CardDescription>
            Controle a coleta automática de dados das variáveis OPC
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex space-x-4">
            <Button
              onClick={() => handleLogging('start')}
              disabled={loading || loggingStatus?.is_logging_active}
              className="flex items-center space-x-2"
            >
              <Play className="h-4 w-4" />
              <span>Iniciar Logging</span>
            </Button>
            <Button
              variant="outline"
              onClick={() => handleLogging('stop')}
              disabled={loading || !loggingStatus?.is_logging_active}
              className="flex items-center space-x-2"
            >
              <Square className="h-4 w-4" />
              <span>Parar Logging</span>
            </Button>
          </div>

          {loggingStatus?.is_logging_active && (
            <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-md">
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium text-green-800 dark:text-green-200">
                  Logging ativo
                </span>
              </div>
              <p className="text-xs text-green-600 dark:text-green-300 mt-1">
                Os dados das variáveis OPC estão sendo coletados automaticamente
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Variables List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Settings className="h-5 w-5" />
            <span>{selectedModel ? 'Variáveis do Modelo' : 'Todas as Variáveis Registradas'}</span>
          </CardTitle>
          <CardDescription>
            {selectedModel
              ? 'Variáveis associadas especificamente a este modelo (Excluir aqui apenas remove a associação)'
              : 'Lista meste de todas as variáveis OPC configuradas para esta linha (Excluir aqui remove do banco de dados)'
            }
          </CardDescription>
        </CardHeader>
        <CardContent>
          {(selectedModel ? variables.filter(v => modelVariables.some(mv => mv.opc_variable_id === v.id)) : variables).length > 0 ? (
            <div className="space-y-4">
              {(selectedModel ? variables.filter(v => modelVariables.some(mv => mv.opc_variable_id === v.id)) : variables).map((variable) => (
                <Card key={variable.id} className="border-l-4 border-l-primary">
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-medium">{variable.variable_name}</h4>
                          <Badge variant="outline">{variable.type}</Badge>
                          <Badge className={`${getBadgeColor(variable.type_category)} border`}>
                            {getBadgeLabel(variable.type_category)}
                          </Badge>
                          <Badge variant={variable.is_active ? 'default' : 'secondary'}>
                            {variable.is_active ? 'Ativa' : 'Inativa'}
                          </Badge>

                          {/* [NOVO] Badge do Modelo */}
                          {selectedModel && modelVariables.find(mv => mv.opc_variable_id === variable.id) && (
                            <Badge className="bg-indigo-500 hover:bg-indigo-600 text-white border-indigo-600">
                              MODELO: {modelVariables.find(mv => mv.opc_variable_id === variable.id).role.toUpperCase()}
                            </Badge>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          <strong>Node ID:</strong> <code>{variable.node_id}</code>
                        </div>
                        {variable.description && (
                          <div className="text-sm text-muted-foreground">
                            <strong>Descrição:</strong> {variable.description}
                          </div>
                        )}
                      </div>

                      <div className="flex space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleEdit(variable)}
                          className="hover:bg-blue-50 hover:border-blue-300 transition-colors duration-200"
                          title="Editar variável"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteClick(variable)}
                          className="text-destructive hover:text-destructive hover:bg-red-50 hover:border-red-300 transition-colors duration-200"
                          title={selectedModel ? "Remover do Modelo" : "Excluir Definitivamente"}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <Settings className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-semibold mb-2">
                {selectedModel ? 'Nenhuma variável associada' : 'Nenhuma variável registrada'}
              </h3>
              <p className="text-muted-foreground mb-4">
                {selectedModel
                  ? 'Este modelo ainda não possui variáveis. Adicione uma nova ou associe existentes.'
                  : `Comece registrando suas primeiras variáveis OPC para a linha ${selectedLine}`
                }
              </p>
              <Button
                onClick={() => setDialogOpen(true)}
                className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-all duration-200 hover:scale-105 hover:shadow-lg"
              >
                <Plus className="h-4 w-4 mr-2 transition-transform duration-200 hover:rotate-90" />
                {selectedModel ? 'Adicionar Variável ao Modelo' : 'Registrar Primeira Variável'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialog de Confirmação de Exclusão */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar {selectedModel ? 'Remoção' : 'Exclusão'}</DialogTitle>
            <DialogDescription>
              {selectedModel ? (
                <span>
                  Tem certeza que deseja remover <strong>{variableToDelete?.variable_name}</strong> deste modelo?
                  <br /><span className="text-indigo-600 dark:text-indigo-400 font-semibold mt-2 block">Isso NÃO excluirá a variável de outros modelos ou da linha.</span>
                </span>
              ) : (
                <span>
                  Tem certeza que deseja excluir <strong>{variableToDelete?.variable_name}</strong>?
                  <br /><span className="text-red-600 dark:text-red-400 font-bold mt-2 block">ATENÇÃO: Esta ação é definitiva e removerá a variável de TODOS os modelos!</span>
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={loading}
              className="transition-all duration-200 hover:scale-105"
            >
              {loading ? (selectedModel ? 'Removendo...' : 'Excluindo...') : (selectedModel ? 'Remover' : 'Excluir')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default OPCConfiguration