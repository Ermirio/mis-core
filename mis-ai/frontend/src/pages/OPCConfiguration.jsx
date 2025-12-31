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

const OPCConfiguration = ({ selectedLine }) => {
  const [variables, setVariables] = useState([])
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
    description: ''
  })
  const { toast } = useToast()

  useEffect(() => {
    if (selectedLine) {
      loadVariables()
      loadLoggingStatus()
    } else {
      setVariables([])
      setLoggingStatus(null)
    }
  }, [selectedLine])

  const loadVariables = async () => {
    try {
      const data = await api.getOPCVariables(selectedLine)
      setVariables(data)
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro ao carregar variáveis OPC",
        variant: "destructive"
      })
    }
  }

  const loadLoggingStatus = async () => {
    try {
      const data = await api.getOPCLoggingStatus(selectedLine)
      setLoggingStatus(data)
    } catch (error) {
      console.error('Erro ao carregar status de logging:', error)
      setLoggingStatus({ is_logging_active: false })
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.node_id.trim() || !formData.variable_name.trim()) {
      toast({
        title: "Erro",
        description: "Node ID e nome da variável são obrigatórios",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      if (editingVariable) {
        await api.updateOPCVariable(editingVariable.id, {
          ...formData,
          line: selectedLine
        })
        toast({
          title: "Sucesso",
          description: "Variável OPC atualizada com sucesso"
        })
      } else {
        await api.createOPCVariable({
          ...formData,
          line: selectedLine
        })
        toast({
          title: "Sucesso",
          description: "Variável OPC registrada com sucesso"
        })
      }
      
      setDialogOpen(false)
      setEditingVariable(null)
      setFormData({
        node_id: '',
        variable_name: '',
        type: 'Float',
        type_category: 'read',
        description: ''
      })
      loadVariables()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || `Erro ao ${editingVariable ? 'atualizar' : 'registrar'} variável OPC`,
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
        toast({
          title: "Sucesso",
          description: "Logging OPC iniciado"
        })
      } else {
        await api.stopOPCLogging(selectedLine)
        toast({
          title: "Sucesso",
          description: "Logging OPC parado"
        })
      }
      loadLoggingStatus()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao controlar logging OPC",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleEdit = (variable) => {
    setEditingVariable(variable)
    setFormData({
      node_id: variable.node_id,
      variable_name: variable.variable_name,
      type: variable.type,
      type_category: variable.type_category || 'read',
      description: variable.description || ''
    })
    setDialogOpen(true)
  }

  const handleDeleteClick = (variable) => {
    setVariableToDelete(variable)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!variableToDelete) return
    
    setLoading(true)
    try {
      await api.deleteOPCVariable(variableToDelete.id)
      toast({
        title: "Sucesso",
        description: "Variável OPC excluída com sucesso"
      })
      setDeleteDialogOpen(false)
      setVariableToDelete(null)
      loadVariables()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao excluir variável OPC",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleOpenChange = (open) => {
    if (!open) {
      setEditingVariable(null)
      setFormData({
        node_id: '',
        variable_name: '',
        type: 'Float',
        type_category: 'read',
        description: ''
      })
    }
    setDialogOpen(open)
  }

  if (!selectedLine) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Configuração OPC</h1>
          <p className="text-muted-foreground">
            Configure variáveis OPC e controle o logging de dados
          </p>
        </div>
        
        <Card>
          <CardContent className="text-center py-12">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhuma linha selecionada</h3>
            <p className="text-muted-foreground">
              Selecione uma linha na barra de navegação para configurar variáveis OPC
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
          <h1 className="text-3xl font-bold">Configuração OPC</h1>
          <p className="text-muted-foreground">
            Configurações OPC para a linha <strong>{selectedLine}</strong>
          </p>
        </div>
        
        <Dialog open={dialogOpen} onOpenChange={handleOpenChange}>
          <DialogTrigger asChild>
            <Button className="flex items-center space-x-2 bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-all duration-200 hover:scale-105 hover:shadow-lg">
              <Plus className="h-4 w-4 transition-transform duration-200 hover:rotate-90" />
              <span>Nova Variável</span>
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
                      <SelectItem value="read">Leitura (Input)</SelectItem>
                      <SelectItem value="write">Escrita (Target/Output)</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formData.type_category === 'read' 
                      ? 'Variável para leitura de dados (sensores, medições)'
                      : 'Variável para escrita de predições (targets, setpoints)'
                    }
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
            <span>Variáveis Registradas</span>
          </CardTitle>
          <CardDescription>
            Lista de variáveis OPC configuradas para esta linha
          </CardDescription>
        </CardHeader>
        <CardContent>
          {variables.length > 0 ? (
            <div className="space-y-4">
              {variables.map((variable) => (
                <Card key={variable.id} className="border-l-4 border-l-primary">
                  <CardContent className="pt-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-medium">{variable.variable_name}</h4>
                          <Badge variant="outline">{variable.type}</Badge>
                          <Badge variant={variable.type_category === 'write' ? 'destructive' : 'default'}>
                            {variable.type_category === 'write' ? '📤 Escrita' : '📥 Leitura'}
                          </Badge>
                          <Badge variant={variable.is_active ? 'default' : 'secondary'}>
                            {variable.is_active ? 'Ativa' : 'Inativa'}
                          </Badge>
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
                          title="Excluir variável"
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
              <h3 className="text-lg font-semibold mb-2">Nenhuma variável registrada</h3>
              <p className="text-muted-foreground mb-4">
                Comece registrando suas primeiras variáveis OPC para a linha {selectedLine}
              </p>
              <Button 
                onClick={() => setDialogOpen(true)}
                className="bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-all duration-200 hover:scale-105 hover:shadow-lg"
              >
                <Plus className="h-4 w-4 mr-2 transition-transform duration-200 hover:rotate-90" />
                Registrar Primeira Variável
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialog de Confirmação de Exclusão */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar Exclusão</DialogTitle>
            <DialogDescription>
              Tem certeza que deseja excluir a variável <strong>{variableToDelete?.variable_name}</strong>?
              Esta ação não pode ser desfeita.
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
              {loading ? 'Excluindo...' : 'Excluir'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default OPCConfiguration