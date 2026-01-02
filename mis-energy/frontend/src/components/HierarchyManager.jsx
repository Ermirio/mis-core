import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import {
  Folder,
  FolderPlus,
  File,
  ChevronRight,
  ChevronDown,
  Plus,
  Trash2,
  Edit,
  Factory,
  Map,
  Layout,
  Server,
  Zap,
  Cpu,
  AlertTriangle,
  Loader2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'

export function HierarchyManager({ onSelect, selectedId, onAddEquipment }) {
  const navigate = useNavigate()
  const [hierarchy, setHierarchy] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingNode, setEditingNode] = useState(null)
  const [parentNode, setParentNode] = useState(null)
  const { toast } = useToast()

  // Delete confirmation dialog states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingNode, setDeletingNode] = useState(null)
  const [deleteInfo, setDeleteInfo] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const handleAddEquipment = (node, e) => {
    e.stopPropagation()
    if (onAddEquipment) {
      onAddEquipment(node)
    } else {
      // Navigate to equipments page with hierarchy pre-selected
      navigate(`/equipments?hierarchy_id=${node.id}&hierarchy_name=${encodeURIComponent(node.name)}`)
    }
  }

  const [formData, setFormData] = useState({
    name: '',
    code: '',
    type: 'factory',
    description: ''
  })

  useEffect(() => {
    fetchHierarchy()
  }, [])

  const fetchHierarchy = async () => {
    try {
      const data = await api.get('/hierarchy/tree')
      if (data.success) {
        setHierarchy(data.data)
      }
    } catch (error) {
      console.error('Erro ao carregar hierarquia:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const handleAdd = (parent = null) => {
    setParentNode(parent)
    setEditingNode(null)
    setFormData({
      name: '',
      code: '',
      type: parent ? getNextType(parent.type) : 'factory',
      description: ''
    })
    setDialogOpen(true)
  }

  const handleEdit = (node, e) => {
    e.stopPropagation()
    setEditingNode(node)
    setFormData({
      name: node.name,
      code: node.code || '',
      type: node.type,
      description: node.description || ''
    })
    setDialogOpen(true)
  }

  const handleDeleteClick = async (node, e) => {
    e.stopPropagation()
    setDeletingNode(node)
    setDeleteLoading(true)
    setDeleteDialogOpen(true)

    try {
      // Buscar informações sobre o que será excluído
      const data = await api.get(`/hierarchy/${node.id}/delete-info`)
      if (data.success) {
        setDeleteInfo(data.data)
      }
    } catch (error) {
      console.error("Erro ao buscar info de exclusão:", error)
      setDeleteInfo({
        name: node.name,
        type_name: node.type,
        children_count: 0,
        equipments_count: 0,
        has_dependencies: false
      })
    } finally {
      setDeleteLoading(false)
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deletingNode) return

    setDeleteLoading(true)
    try {
      // Usar ?force=true para confirmar a exclusão
      const data = await api.delete(`/hierarchy/${deletingNode.id}?force=true`)

      if (data.success) {
        toast({
          title: 'Removido com sucesso',
          description: data.message
        })
        setDeleteDialogOpen(false)
        setDeletingNode(null)
        setDeleteInfo(null)
        fetchHierarchy()
      }
    } catch (error) {
      console.error("Erro ao remover:", error)
      toast({
        title: 'Erro ao remover',
        description: error.response?.data?.error || 'Erro desconhecido',
        variant: 'destructive'
      })
    } finally {
      setDeleteLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    try {
      const url = editingNode ? `/hierarchy/${editingNode.id}` : '/hierarchy'

      const body = {
        ...formData,
        parent_id: parentNode ? parentNode.id : (editingNode ? editingNode.parent_id : null)
      }

      let data;
      if (editingNode) {
        data = await api.put(url, body);
      } else {
        data = await api.post(url, body);
      }

      if (data.success) {
        toast({ title: editingNode ? 'Atualizado' : 'Criado com sucesso' })
        setDialogOpen(false)
        fetchHierarchy()
      }
    } catch (error) {
      console.error('Erro ao salvar:', error)
      toast({ title: 'Erro', description: 'Não foi possível salvar.', variant: 'destructive' })
    }
  }

  const getNextType = (currentType) => {
    // Retorna o próximo tipo permitido na hierarquia ISA-95
    // Fábrica → Área → Linha → Grupo de Máquinas (não pode ter mais filhos estruturais)
    switch (currentType) {
      case 'factory': return 'area'
      case 'area': return 'line'
      case 'line': return 'machine_group'
      case 'machine_group': return null // Grupo só pode ter equipamentos, não sublocalizações
      default: return 'factory'
    }
  }

  // Retorna os tipos permitidos para criar como filho de um parent
  const getAllowedChildTypes = (parentType) => {
    switch (parentType) {
      case 'factory': return ['area'] // Fábrica só pode ter áreas
      case 'area': return ['line'] // Área só pode ter linhas
      case 'line': return ['machine_group'] // Linha só pode ter grupos de máquinas
      case 'machine_group': return [] // Grupo só pode ter equipamentos (não locais)
      default: return ['factory']
    }
  }

  // Verifica se pode adicionar sublocalização a um nó
  const canAddChild = (parentType) => {
    return getAllowedChildTypes(parentType).length > 0
  }

  const getTypeIcon = (type) => {
    switch (type) {
      case 'factory': return <Factory className="h-4 w-4 text-purple-500" />
      case 'area': return <Map className="h-4 w-4 text-blue-500" />
      case 'line': return <Layout className="h-4 w-4 text-orange-500" />
      case 'machine_group': return <Server className="h-4 w-4 text-cyan-500" />
      case 'equipment': return <Zap className="h-4 w-4 text-yellow-500" />
      default: return <Cpu className="h-4 w-4 text-slate-400" />
    }
  }

  const getTypeBgColor = (type) => {
    switch (type) {
      case 'factory': return 'bg-purple-50 dark:bg-purple-900/20'
      case 'area': return 'bg-blue-50 dark:bg-blue-900/20'
      case 'line': return 'bg-orange-50 dark:bg-orange-900/20'
      case 'machine_group': return 'bg-cyan-50 dark:bg-cyan-900/20'
      case 'equipment': return 'bg-yellow-50 dark:bg-yellow-900/20'
      default: return 'bg-slate-50 dark:bg-slate-800/20'
    }
  }

  const countAllChildren = (node) => {
    if (!node.children || node.children.length === 0) return 0
    return node.children.reduce((acc, child) => acc + 1 + countAllChildren(child), 0)
  }

  const expandAll = () => {
    const allIds = {}
    const traverse = (nodes) => {
      nodes.forEach(node => {
        if (node.children && node.children.length > 0) {
          allIds[node.id] = true
          traverse(node.children)
        }
      })
    }
    traverse(hierarchy)
    setExpanded(allIds)
  }

  const collapseAll = () => {
    setExpanded({})
  }

  const renderTree = (nodes, level = 0) => {
    return nodes.map(node => {
      const hasChildren = node.children && node.children.length > 0
      const isExpanded = expanded[node.id]
      const childCount = countAllChildren(node)
      const isEquipment = node.type === 'equipment'

      return (
        <div key={node.id} className="select-none">
          <div
            className={cn(
              "group flex items-center py-2 px-3 rounded-lg cursor-pointer transition-all duration-200",
              "hover:bg-slate-100 dark:hover:bg-slate-800 hover:shadow-sm",
              selectedId === node.id && "bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/30 border-l-4 border-blue-500 shadow-sm"
            )}
            style={{ marginLeft: `${level * 1.25}rem` }}
            onClick={() => onSelect && onSelect(node)}
          >
            {/* Expand/Collapse Button */}
            <div
              className={cn(
                "p-1.5 mr-2 rounded-md transition-all duration-200",
                hasChildren && "hover:bg-slate-200 dark:hover:bg-slate-700 cursor-pointer"
              )}
              onClick={(e) => { e.stopPropagation(); if (hasChildren) toggleExpand(node.id); }}
            >
              {hasChildren ? (
                <ChevronRight className={cn(
                  "h-4 w-4 transition-transform duration-300 ease-out text-slate-400",
                  isExpanded && "rotate-90"
                )} />
              ) : <div className="w-4 h-4" />}
            </div>

            {/* Type Icon with Background */}
            <div className={cn(
              "p-1.5 rounded-lg mr-3",
              getTypeBgColor(node.type)
            )}>
              {getTypeIcon(node.type)}
            </div>

            {/* Node Name and Info */}
            <div className="flex-1 min-w-0 overflow-visible">
              <span
                className="text-sm font-medium text-slate-700 dark:text-slate-200 block leading-tight"
                title={node.name}
              >
                {node.name}
              </span>
              {node.code && (
                <span className="text-xs text-slate-400 dark:text-slate-500">{node.code}</span>
              )}
            </div>

            {/* Child Count Badge */}
            {hasChildren && !isExpanded && childCount > 0 && (
              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 mr-2">
                {childCount}
              </span>
            )}

            {/* Action Buttons - Visible on Hover */}
            {!isEquipment && (
              <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-all duration-200">
                {/* Botão de sublocalização - oculto para grupos de máquinas (só podem ter equipamentos) */}
                {canAddChild(node.type) && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 hover:bg-green-100 hover:text-green-600 dark:hover:bg-green-900/30"
                    onClick={(e) => { e.stopPropagation(); handleAdd(node); }}
                    title={`Adicionar ${getNextType(node.type) === 'area' ? 'Área' : getNextType(node.type) === 'line' ? 'Linha' : 'Grupo de Máquinas'}`}
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 hover:bg-yellow-100 hover:text-yellow-600 dark:hover:bg-yellow-900/30"
                  onClick={(e) => handleAddEquipment(node, e)}
                  title="Adicionar equipamento/medidor"
                >
                  <Zap className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 hover:bg-blue-100 hover:text-blue-600 dark:hover:bg-blue-900/30"
                  onClick={(e) => handleEdit(node, e)}
                  title="Editar"
                >
                  <Edit className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30"
                  onClick={(e) => handleDeleteClick(node, e)}
                  title="Remover"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </div>

          {/* Children with Animation */}
          <div className={cn(
            "overflow-hidden transition-all duration-300 ease-out",
            isExpanded ? "max-h-[2000px] opacity-100" : "max-h-0 opacity-0"
          )}>
            {hasChildren && renderTree(node.children, level + 1)}
          </div>
        </div>
      )
    })
  }

  return (
    <div className="border rounded-xl p-4 bg-white dark:bg-slate-950 shadow-sm">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100 dark:border-slate-800">
        <h3 className="font-semibold text-lg text-slate-800 dark:text-slate-100">Hierarquia</h3>
        <div className="flex items-center space-x-2">
          {hierarchy.length > 0 && (
            <>
              <Button
                size="sm"
                variant="ghost"
                onClick={expandAll}
                className="text-xs text-slate-500 hover:text-slate-700"
                title="Expandir todos"
              >
                <ChevronDown className="h-3 w-3 mr-1" />
                Expandir
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={collapseAll}
                className="text-xs text-slate-500 hover:text-slate-700"
                title="Recolher todos"
              >
                <ChevronRight className="h-3 w-3 mr-1" />
                Recolher
              </Button>
              <div className="w-px h-5 bg-slate-200 dark:bg-slate-700" />
            </>
          )}
          <Button size="sm" variant="default" onClick={() => handleAdd(null)} className="bg-purple-600 hover:bg-purple-700">
            <Plus className="h-4 w-4 mr-2" />
            Nova Fábrica
          </Button>
        </div>
      </div>

      <div className="space-y-1 max-h-[400px] overflow-y-auto">
        {loading ? (
          <div className="text-center py-4 text-slate-500">Carregando...</div>
        ) : hierarchy.length > 0 ? (
          renderTree(hierarchy)
        ) : (
          <div className="text-center py-8 text-slate-500">
            Nenhuma hierarquia definida.
          </div>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingNode ? 'Editar Local' : 'Novo Local'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Nome</Label>
              <Input
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
                required
                placeholder="Ex: Fábrica Principal"
              />
            </div>
            <div className="space-y-2">
              <Label>Código (Tag Prefix)</Label>
              <Input
                value={formData.code || ''}
                onChange={e => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                placeholder="Ex: FAC1"
                maxLength={10}
              />
              <p className="text-xs text-slate-500">Usado para gerar tags automáticas (ex: FAC1-LIN2...)</p>
            </div>
            <div className="space-y-2">
              <Label>Tipo</Label>
              {/* Quando criando como filho, só mostrar os tipos permitidos */}
              {parentNode ? (
                <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg border">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {formData.type === 'area' && '📍 Área'}
                    {formData.type === 'line' && '📏 Linha'}
                    {formData.type === 'machine_group' && '📊 Grupo de Máquinas'}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Será criado dentro de: {parentNode.name}
                  </p>
                </div>
              ) : editingNode ? (
                <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg border">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {formData.type === 'factory' && '🏭 Fábrica'}
                    {formData.type === 'area' && '📍 Área'}
                    {formData.type === 'line' && '📏 Linha'}
                    {formData.type === 'machine_group' && '📊 Grupo de Máquinas'}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Tipo não pode ser alterado após criação
                  </p>
                </div>
              ) : (
                <Select
                  value={formData.type}
                  onValueChange={v => setFormData({ ...formData, type: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="factory">🏭 Fábrica</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="space-y-2">
              <Label>Descrição</Label>
              <Input
                value={formData.description}
                onChange={e => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            <DialogFooter>
              <Button type="submit">Salvar</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
        if (!open) {
          setDeleteDialogOpen(false)
          setDeletingNode(null)
          setDeleteInfo(null)
        }
      }}>
        <DialogContent className="sm:max-w-[450px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              Confirmar Exclusão
            </DialogTitle>
            <DialogDescription>
              Esta ação não pode ser desfeita.
            </DialogDescription>
          </DialogHeader>

          {deleteLoading && !deleteInfo ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : deleteInfo && (
            <div className="space-y-4 py-4">
              <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  Você está prestes a excluir:
                </p>
                <p className="text-lg font-semibold text-slate-900 dark:text-slate-100 mt-1">
                  {deleteInfo.type_name}: {deleteInfo.name}
                </p>
              </div>

              {deleteInfo.has_dependencies && (
                <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                  <p className="text-sm font-medium text-amber-800 dark:text-amber-200 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Atenção! Itens que serão afetados:
                  </p>
                  <ul className="list-disc list-inside mt-2 text-sm text-amber-700 dark:text-amber-300 space-y-1">
                    {deleteInfo.children_count > 0 && (
                      <li>
                        <strong>{deleteInfo.children_count}</strong> sublocalização(ões) (áreas, linhas, grupos)
                      </li>
                    )}
                    {deleteInfo.equipments_count > 0 && (
                      <li>
                        <strong>{deleteInfo.equipments_count}</strong> equipamento(s) serão desassociados
                      </li>
                    )}
                  </ul>
                </div>
              )}

              {!deleteInfo.has_dependencies && (
                <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                  <p className="text-sm text-green-700 dark:text-green-300">
                    ✓ Este item não possui dependências e pode ser excluído com segurança.
                  </p>
                </div>
              )}
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                setDeleteDialogOpen(false)
                setDeletingNode(null)
                setDeleteInfo(null)
              }}
              disabled={deleteLoading}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleteLoading || !deleteInfo}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleteLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Excluindo...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Excluir {deleteInfo?.has_dependencies ? 'Tudo' : ''}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
