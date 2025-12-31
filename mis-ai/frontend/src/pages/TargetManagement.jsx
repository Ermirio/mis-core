import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Target, Plus, Edit, Trash2, AlertCircle, MoreVertical, ToggleLeft, ToggleRight } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

const TargetManagement = ({ selectedLine, setSelectedTarget, onDataChange }) => {
  const [targets, setTargets] = useState([])
  const [loading, setLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  // ADICIONADO: Estados para controlar a janela de edição
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingTarget, setEditingTarget] = useState(null)

  const [formData, setFormData] = useState({
    target_name: '',
    target_unit: '',
    description: ''
  })
  const { toast } = useToast()

  useEffect(() => {
    if (selectedLine) {
      loadTargets()
    } else {
      setTargets([])
    }
  }, [selectedLine])

  const loadTargets = async () => {
    try {
      const data = await api.getTargets(selectedLine)
      setTargets(data || []) // Garante que targets seja sempre um array
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro ao carregar targets",
        variant: "destructive"
      })
    }
  }

  // Renomeado para handleCreateSubmit para clareza
  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    if (!formData.target_name.trim()) {
      toast({
        title: "Erro",
        description: "Nome do target é obrigatório",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      await api.createTarget({
        ...formData,
        line_name: selectedLine
      })
      toast({
        title: "Sucesso",
        description: "Target criado com sucesso"
      })
      setDialogOpen(false)
      resetForm()
      loadTargets()
      if (onDataChange) onDataChange() // <-- Atualiza Navbar
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao criar target",
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

  const handleSelectTarget = (target) => {
    // Só seleciona se estiver ativo
    if (target.is_active) {
      setSelectedTarget(target)
      toast({
        title: "Target Selecionado",
        description: `${target.target_name} foi selecionado como target ativo`
      })
    } else {
      toast({
        title: "Aviso",
        description: `O target "${target.target_name}" está inativo e não pode ser selecionado.`,
        variant: "default"
      })
    }
  }

  // ADIÇÃO: Novas funções para gerenciar os cards
  const resetForm = () => {
    setFormData({ target_name: '', target_unit: '', description: '' })
  }

  const handleEditClick = (target) => {
    setEditingTarget(target)
    setFormData({
      target_name: target.target_name,
      target_unit: target.target_unit || '',
      description: target.description || ''
    })
    setEditDialogOpen(true)
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!formData.target_name.trim()) {
      toast({ title: "Erro", description: "Nome do target é obrigatório", variant: "destructive" })
      return
    }
    setLoading(true)
    try {
      await api.updateTarget(editingTarget.id, formData)
      toast({ title: "Sucesso", description: "Target atualizado com sucesso" })
      setEditDialogOpen(false)
      resetForm()
      loadTargets()
      if (onDataChange) onDataChange() // <-- Atualiza Navbar
    } catch (error) {
      toast({ title: "Erro", description: error.message || "Erro ao atualizar target", variant: "destructive" })
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (targetId) => {
    try {
      await api.deleteTarget(targetId)
      toast({ title: "Sucesso", description: "Target excluído com sucesso" })
      loadTargets()
      if (onDataChange) onDataChange() // <-- Atualiza Navbar
    } catch (error) {
      toast({ title: "Erro", description: error.message || "Erro ao excluir target", variant: "destructive" })
    }
  }

  const handleToggleStatus = async (target) => {
    try {
      await api.updateTarget(target.id, { is_active: !target.is_active })
      toast({ title: "Sucesso", description: `Status do target "${target.target_name}" alterado com sucesso` })
      loadTargets()
    } catch (error) {
      toast({ title: "Erro", description: error.message || "Erro ao alterar status do target", variant: "destructive" })
    }
  }


  if (!selectedLine) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Gerenciamento de Targets</h1>
          <p className="text-muted-foreground">
            Gerencie os targets de predição para cada linha
          </p>
        </div>

        <Card>
          <CardContent className="text-center py-12">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhuma linha selecionada</h3>
            <p className="text-muted-foreground">
              Selecione uma linha na barra de navegação para gerenciar seus targets
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
          <h1 className="text-3xl font-bold">Gerenciamento de Targets</h1>
          <p className="text-muted-foreground">
            Targets de predição para a linha <strong>{selectedLine}</strong>
          </p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            {/* CORREÇÃO VISUAL: Botão com estilo explícito */}
            <Button className="flex items-center space-x-2 bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600">
              <Plus className="h-4 w-4" />
              <span>Novo Target</span>
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Criar Novo Target</DialogTitle>
              <DialogDescription>
                Adicione um novo target de predição para a linha {selectedLine}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateSubmit}>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="target_name">Nome do Target *</Label>
                  <Input id="target_name" value={formData.target_name} onChange={(e) => handleInputChange('target_name', e.target.value)} placeholder="Ex: Densidade, Temperatura, Pressão..." required />
                </div>
                <div>
                  <Label htmlFor="target_unit">Unidade</Label>
                  <Input id="target_unit" value={formData.target_unit} onChange={(e) => handleInputChange('target_unit', e.target.value)} placeholder="Ex: g/cm³, °C, bar, %..." />
                </div>
                <div>
                  <Label htmlFor="description">Descrição</Label>
                  <Textarea id="description" value={formData.description} onChange={(e) => handleInputChange('description', e.target.value)} placeholder="Descrição do que será predito..." rows={3} />
                </div>
              </div>
              <DialogFooter className="mt-6">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
                <Button type="submit" disabled={loading}>{loading ? 'Criando...' : 'Criar Target'}</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* ADIÇÃO: Janela de diálogo para edição */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar Target</DialogTitle>
            <DialogDescription>
              Edite as informações do target {editingTarget?.target_name}.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div><Label htmlFor="edit_target_name">Nome do Target *</Label><Input id="edit_target_name" value={formData.target_name} onChange={(e) => handleInputChange('target_name', e.target.value)} required /></div>
            <div><Label htmlFor="edit_target_unit">Unidade</Label><Input id="edit_target_unit" value={formData.target_unit} onChange={(e) => handleInputChange('target_unit', e.target.value)} /></div>
            <div><Label htmlFor="edit_description">Descrição</Label><Textarea id="edit_description" value={formData.description} onChange={(e) => handleInputChange('description', e.target.value)} rows={3} /></div>
            <DialogFooter className="mt-4">
              <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={loading}>{loading ? 'Salvando...' : 'Salvar Alterações'}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>


      {/* Targets Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {targets.map((target) => (
          // SUBSTITUIÇÃO: Card com funcionalidade completa
          <Card key={target.id} className={`transition-all hover:shadow-lg ${!target.is_active ? 'opacity-50 bg-muted/50' : ''}`}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center space-x-2 cursor-pointer" onClick={() => handleSelectTarget(target)}>
                  <Target className="h-5 w-5 text-primary" />
                  <span>{target.target_name}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge variant={target.is_active ? 'default' : 'secondary'}>{target.is_active ? 'Ativo' : 'Inativo'}</Badge>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild><Button variant="ghost" size="sm" className="h-8 w-8 p-0"><MoreVertical className="h-4 w-4" /></Button></DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleEditClick(target)}><Edit className="h-4 w-4 mr-2" />Editar</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleToggleStatus(target)}>
                        {target.is_active ? <ToggleLeft className="h-4 w-4 mr-2" /> : <ToggleRight className="h-4 w-4 mr-2" />}
                        {target.is_active ? 'Desativar' : 'Ativar'}
                      </DropdownMenuItem>
                      <AlertDialog>
                        <AlertDialogTrigger asChild><DropdownMenuItem className="text-destructive focus:text-destructive" onSelect={(e) => e.preventDefault()}><Trash2 className="h-4 w-4 mr-2" />Excluir</DropdownMenuItem></AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader><AlertDialogTitle>Confirmar Exclusão</AlertDialogTitle><AlertDialogDescription>Tem certeza que deseja excluir permanentemente o target "{target.target_name}"? Esta ação é irreversível.</AlertDialogDescription></AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancelar</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(target.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Excluir Permanentemente</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardTitle>
              <CardDescription>{target.description || 'Sem descrição'}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-muted-foreground">
                <div><strong>Unidade:</strong> {target.target_unit || 'Não definida'}</div>
                <div><strong>Criado em:</strong> {new Date(target.created_at).toLocaleDateString('pt-BR')}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {targets.length === 0 && (
        <Card>
          <CardContent className="text-center py-12">
            <Target className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhum target encontrado</h3>
            <p className="text-muted-foreground mb-4">
              Comece criando seu primeiro target de predição para a linha {selectedLine}
            </p>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Primeiro Target
                </Button>
              </DialogTrigger>
            </Dialog>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default TargetManagement