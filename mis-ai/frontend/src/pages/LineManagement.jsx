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
import { Factory, Plus, Edit, Trash2, MoreVertical, ToggleLeft, ToggleRight } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

const LineManagement = ({ onDataChange }) => {
  const [lines, setLines] = useState([])
  const [loading, setLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingLine, setEditingLine] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    description: ''
  })
  const { toast } = useToast()

  useEffect(() => {
    loadLines()
  }, [])

  const loadLines = async () => {
    try {
      const data = await api.getLines()
      setLines(data)
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro ao carregar linhas",
        variant: "destructive"
      })
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      toast({
        title: "Erro",
        description: "Nome da linha é obrigatório",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      await api.createLine(formData)
      toast({
        title: "Sucesso",
        description: "Linha criada com sucesso"
      })
      setDialogOpen(false)
      resetForm()
      loadLines()
      if (onDataChange) onDataChange() // <-- Atualiza Navbar
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao criar linha",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      toast({
        title: "Erro",
        description: "Nome da linha é obrigatório",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      await api.updateLine(editingLine.id, formData)
      toast({
        title: "Sucesso",
        description: "Linha atualizada com sucesso"
      })
      setEditDialogOpen(false)
      setEditingLine(null)
      resetForm()
      loadLines()
      if (onDataChange) onDataChange() // <-- Atualiza Navbar
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao atualizar linha",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (line) => {
    setEditingLine(line)
    setFormData({
      name: line.name,
      description: line.description || ''
    })
    setEditDialogOpen(true)
  }

  const handleDelete = async (lineId) => {
    try {
      await api.deleteLine(lineId)
      toast({
        title: "Sucesso",
        description: "Linha excluída com sucesso"
      })
      loadLines()
      if (onDataChange) onDataChange() // <-- Atualiza Navbar
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao excluir linha",
        variant: "destructive"
      })
    }
  }

  const handleToggleStatus = async (line) => {
    try {
      await api.updateLine(line.id, { is_active: !line.is_active })
      toast({
        title: "Sucesso",
        description: `Status da linha "${line.name}" alterado com sucesso`
      })
      loadLines()
    } catch (error) {
      toast({
        title: "Erro",
        description: error.message || "Erro ao alterar status da linha",
        variant: "destructive"
      })
    }
  }

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const resetForm = () => {
    setFormData({ name: '', description: '' })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Gerenciamento de Linhas</h1>
          <p className="text-muted-foreground">Adicione, edite e gerencie as linhas de produção</p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            {/* <-- CORREÇÃO: Aplicadas classes de cor explícitas que não dependem do tema --> */}
            <Button className="flex items-center space-x-2 bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600">
              <Plus className="h-4 w-4" />
              <span>Nova Linha</span>
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Criar Nova Linha</DialogTitle><DialogDescription>Adicione uma nova linha de produção ao sistema.</DialogDescription></DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div><Label htmlFor="name">Nome da Linha *</Label><Input id="name" value={formData.name} onChange={(e) => handleInputChange('name', e.target.value)} placeholder="Ex: L01, L02, Linha A..." required /></div>
              <div><Label htmlFor="description">Descrição</Label><Textarea id="description" value={formData.description} onChange={(e) => handleInputChange('description', e.target.value)} placeholder="Descrição opcional da linha..." rows={3} /></div>
              <DialogFooter className="mt-4"><Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button><Button type="submit" disabled={loading}>{loading ? 'Criando...' : 'Criar Linha'}</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Editar Linha</DialogTitle><DialogDescription>Edite as informações da linha {editingLine?.name}.</DialogDescription></DialogHeader>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div><Label htmlFor="edit_name">Nome da Linha *</Label><Input id="edit_name" value={formData.name} onChange={(e) => handleInputChange('name', e.target.value)} required /></div>
            <div><Label htmlFor="edit_description">Descrição</Label><Textarea id="edit_description" value={formData.description} onChange={(e) => handleInputChange('description', e.target.value)} rows={3} /></div>
            <DialogFooter className="mt-4"><Button type="button" variant="outline" onClick={() => { setEditDialogOpen(false); setEditingLine(null); resetForm(); }}>Cancelar</Button><Button type="submit" disabled={loading}>{loading ? 'Salvando...' : 'Salvar Alterações'}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {lines.map((line) => (
          <Card key={line.id} className={`transition-all hover:shadow-lg ${!line.is_active ? 'opacity-50 bg-muted/50' : ''}`}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center space-x-2"><Factory className="h-5 w-5 text-primary" /><span>{line.name}</span></div>
                <div className="flex items-center space-x-2">
                  <Badge variant={line.is_active ? 'default' : 'secondary'}>{line.is_active ? 'Ativa' : 'Inativa'}</Badge>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild><Button variant="ghost" size="sm" className="h-8 w-8 p-0"><MoreVertical className="h-4 w-4" /></Button></DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleEdit(line)}><Edit className="h-4 w-4 mr-2" />Editar</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleToggleStatus(line)}>
                        {line.is_active ? <ToggleLeft className="h-4 w-4 mr-2" /> : <ToggleRight className="h-4 w-4 mr-2" />}
                        {line.is_active ? 'Desativar' : 'Ativar'}
                      </DropdownMenuItem>
                      <AlertDialog>
                        <AlertDialogTrigger asChild><DropdownMenuItem className="text-destructive focus:text-destructive" onSelect={(e) => e.preventDefault()}><Trash2 className="h-4 w-4 mr-2" />Excluir</DropdownMenuItem></AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader><AlertDialogTitle>Confirmar Exclusão</AlertDialogTitle>
                            <AlertDialogDescription>
                              Tem certeza que deseja excluir permanentemente a linha "{line.name}"? Esta ação é irreversível e removerá a linha do banco de dados.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancelar</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(line.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Excluir Permanentemente</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardTitle>
              <CardDescription>{line.description || 'Sem descrição'}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-muted-foreground">
                <div><strong>ID:</strong> {line.id}</div>
                {line.created_at && <div><strong>Criada em:</strong> {new Date(line.created_at).toLocaleDateString('pt-BR')}</div>}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {lines.length === 0 && (
        <Card>
          <CardContent className="text-center py-12">
            <Factory className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhuma linha encontrada</h3>
            <p className="text-muted-foreground mb-4">Comece criando sua primeira linha de produção.</p>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}><DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" />Criar Primeira Linha</Button></DialogTrigger></Dialog>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default LineManagement