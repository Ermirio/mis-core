import { useState, useEffect } from 'react'
import api from '../services/api'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { useToast } from '@/hooks/use-toast'

export function HierarchySelector({ onSelect, selectedId }) {
    const [hierarchy, setHierarchy] = useState([])
    const [loading, setLoading] = useState(true)
    const { toast } = useToast()

    // Selection states
    const [selectedFactory, setSelectedFactory] = useState(null)
    const [selectedArea, setSelectedArea] = useState(null)
    const [selectedLine, setSelectedLine] = useState(null)
    const [selectedMachineGroup, setSelectedMachineGroup] = useState(null)

    // Create dialog states
    const [createDialogOpen, setCreateDialogOpen] = useState(false)
    const [createType, setCreateType] = useState(null) // 'area', 'line', 'machine_group'
    const [createParent, setCreateParent] = useState(null)
    const [newName, setNewName] = useState('')
    const [newCode, setNewCode] = useState('')
    const [creating, setCreating] = useState(false)

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

    // Helper to find node by ID in tree
    const findNode = (nodes, id) => {
        for (const node of nodes) {
            if (node.id === id) return node
            if (node.children) {
                const found = findNode(node.children, id)
                if (found) return found
            }
        }
        return null
    }

    // Handle selection changes
    const handleFactoryChange = (value) => {
        const factory = hierarchy.find(h => h.id.toString() === value)
        setSelectedFactory(factory)
        setSelectedArea(null)
        setSelectedLine(null)
        setSelectedMachineGroup(null)
        onSelect(factory)
    }

    const handleAreaChange = (value) => {
        const area = selectedFactory?.children?.find(a => a.id.toString() === value)
        setSelectedArea(area)
        setSelectedLine(null)
        setSelectedMachineGroup(null)
        onSelect(area)
    }

    const handleLineChange = (value) => {
        const line = selectedArea?.children?.find(l => l.id.toString() === value)
        setSelectedLine(line)
        setSelectedMachineGroup(null)
        onSelect(line)
    }

    const handleMachineGroupChange = (value) => {
        const group = selectedLine?.children?.find(g => g.id.toString() === value)
        setSelectedMachineGroup(group)
        onSelect(group)
    }

    // Handle inline creation
    const openCreateDialog = (type, parent) => {
        setCreateType(type)
        setCreateParent(parent)
        setNewName('')
        setNewCode('')
        setCreateDialogOpen(true)
    }

    const handleCreate = async () => {
        if (!newName.trim()) {
            toast({ title: 'Nome é obrigatório', variant: 'destructive' })
            return
        }

        setCreating(true)
        try {
            const payload = {
                name: newName.trim(),
                code: newCode.trim().toUpperCase() || null,
                type: createType,
                parent_id: createParent?.id || null
            }

            const data = await api.post('/hierarchy', payload)

            if (data.success) {
                toast({ title: `${getTypeLabel(createType)} criado(a) com sucesso!` })
                setCreateDialogOpen(false)

                // Save current parent IDs before refresh
                const currentFactoryId = selectedFactory?.id
                const currentAreaId = selectedArea?.id
                const currentLineId = selectedLine?.id

                // Refresh hierarchy
                const refreshData = await api.get('/hierarchy/tree')
                if (refreshData.success) {
                    setHierarchy(refreshData.data)

                    // Re-sync selections after refresh
                    setTimeout(() => {
                        // Find and restore factory
                        const restoredFactory = refreshData.data.find(f => f.id === currentFactoryId)
                        if (restoredFactory) {
                            setSelectedFactory(restoredFactory)

                            // Find and restore area
                            const restoredArea = restoredFactory.children?.find(a => a.id === currentAreaId)
                            let restoredLine = null

                            if (restoredArea) {
                                setSelectedArea(restoredArea)

                                // Find and restore line
                                restoredLine = restoredArea.children?.find(l => l.id === currentLineId)
                                if (restoredLine) {
                                    setSelectedLine(restoredLine)
                                }
                            }

                            // Auto-select the new node
                            const newNode = data.data
                            if (createType === 'area' && newNode) {
                                const foundArea = restoredFactory.children?.find(a => a.id === newNode.id)
                                if (foundArea) {
                                    setSelectedArea(foundArea)
                                    onSelect(foundArea)
                                }
                            } else if (createType === 'line' && newNode && restoredArea) {
                                const foundLine = restoredArea.children?.find(l => l.id === newNode.id)
                                if (foundLine) {
                                    setSelectedLine(foundLine)
                                    onSelect(foundLine)
                                }
                            } else if (createType === 'machine_group' && newNode && restoredLine) {
                                const foundGroup = restoredLine.children?.find(g => g.id === newNode.id)
                                if (foundGroup) {
                                    setSelectedMachineGroup(foundGroup)
                                    onSelect(foundGroup)
                                }
                            }
                        }
                    }, 100)
                }
            }
        } catch (error) {
            console.error('Erro ao criar:', error)
            toast({ title: 'Erro ao criar', variant: 'destructive' })
        } finally {
            setCreating(false)
        }
    }

    const getTypeLabel = (type) => {
        switch (type) {
            case 'area': return 'Área'
            case 'line': return 'Linha'
            case 'machine_group': return 'Grupo de Máquinas'
            default: return 'Item'
        }
    }

    if (loading) return <div className="text-sm text-slate-500">Carregando locais...</div>

    return (
        <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Factory Select */}
                <div className="space-y-1">
                    <Label className="text-xs text-slate-500">Fábrica</Label>
                    <Select onValueChange={handleFactoryChange} value={selectedFactory?.id?.toString()}>
                        <SelectTrigger>
                            <SelectValue placeholder="Selecione a Fábrica" />
                        </SelectTrigger>
                        <SelectContent>
                            {hierarchy.filter(n => n.type === 'factory').map(factory => (
                                <SelectItem key={factory.id} value={factory.id.toString()}>
                                    {factory.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Area Select with Add Button */}
                <div className="space-y-1">
                    <Label className="text-xs text-slate-500">Área</Label>
                    <div className="flex gap-1">
                        <Select
                            onValueChange={handleAreaChange}
                            value={selectedArea?.id?.toString()}
                            disabled={!selectedFactory}
                        >
                            <SelectTrigger className="flex-1">
                                <SelectValue placeholder={selectedFactory ? "Selecione a Área" : "Selecione a Fábrica primeiro"} />
                            </SelectTrigger>
                            <SelectContent>
                                {selectedFactory?.children?.filter(c => c.type !== 'equipment').map(area => (
                                    <SelectItem key={area.id} value={area.id.toString()}>
                                        {area.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="h-10 w-10 shrink-0 border-dashed hover:bg-blue-50 hover:text-blue-600 hover:border-blue-300"
                            onClick={() => openCreateDialog('area', selectedFactory)}
                            disabled={!selectedFactory}
                            title="Criar nova Área"
                        >
                            <Plus className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                {/* Line Select with Add Button */}
                <div className="space-y-1">
                    <Label className="text-xs text-slate-500">Linha</Label>
                    <div className="flex gap-1">
                        <Select
                            onValueChange={handleLineChange}
                            value={selectedLine?.id?.toString()}
                            disabled={!selectedArea}
                        >
                            <SelectTrigger className="flex-1">
                                <SelectValue placeholder={selectedArea ? "Selecione a Linha" : "Selecione a Área primeiro"} />
                            </SelectTrigger>
                            <SelectContent>
                                {selectedArea?.children?.filter(c => c.type !== 'equipment').map(line => (
                                    <SelectItem key={line.id} value={line.id.toString()}>
                                        {line.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="h-10 w-10 shrink-0 border-dashed hover:bg-orange-50 hover:text-orange-600 hover:border-orange-300"
                            onClick={() => openCreateDialog('line', selectedArea)}
                            disabled={!selectedArea}
                            title="Criar nova Linha"
                        >
                            <Plus className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                {/* Machine Group Select with Add Button */}
                <div className="space-y-1">
                    <Label className="text-xs text-slate-500">Grupo de Máquinas (Opcional)</Label>
                    <div className="flex gap-1">
                        <Select
                            onValueChange={handleMachineGroupChange}
                            value={selectedMachineGroup?.id?.toString()}
                            disabled={!selectedLine}
                        >
                            <SelectTrigger className="flex-1">
                                <SelectValue placeholder={selectedLine ? "Selecione o Grupo" : "Selecione a Linha primeiro"} />
                            </SelectTrigger>
                            <SelectContent>
                                {selectedLine?.children?.filter(c => c.type !== 'equipment').map(group => (
                                    <SelectItem key={group.id} value={group.id.toString()}>
                                        {group.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="h-10 w-10 shrink-0 border-dashed hover:bg-cyan-50 hover:text-cyan-600 hover:border-cyan-300"
                            onClick={() => openCreateDialog('machine_group', selectedLine)}
                            disabled={!selectedLine}
                            title="Criar novo Grupo de Máquinas"
                        >
                            <Plus className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Hierarchy Level Indicator */}
            {selectedFactory && (
                <div className={`p-3 rounded-lg border-2 ${selectedMachineGroup ? 'bg-purple-50 border-purple-200 dark:bg-purple-900/20 dark:border-purple-800' :
                        selectedLine ? 'bg-orange-50 border-orange-200 dark:bg-orange-900/20 dark:border-orange-800' :
                            selectedArea ? 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800' :
                                'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
                    }`}>
                    <p className="text-sm font-medium">
                        {selectedMachineGroup ? (
                            <span className="text-purple-700 dark:text-purple-300">
                                📊 Medidor de <strong>Grupo de Máquinas</strong>
                            </span>
                        ) : selectedLine ? (
                            <span className="text-orange-700 dark:text-orange-300">
                                📏 Medidor de <strong>Linha</strong>
                            </span>
                        ) : selectedArea ? (
                            <span className="text-blue-700 dark:text-blue-300">
                                📍 Medidor <strong>Setorial</strong> (Área)
                            </span>
                        ) : (
                            <span className="text-green-700 dark:text-green-300">
                                🏭 Medidor de <strong>Entrada</strong> (Fábrica)
                            </span>
                        )}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                        {selectedMachineGroup ? selectedFactory.name + ' > ' + selectedArea.name + ' > ' + selectedLine.name + ' > ' + selectedMachineGroup.name :
                            selectedLine ? selectedFactory.name + ' > ' + selectedArea.name + ' > ' + selectedLine.name :
                                selectedArea ? selectedFactory.name + ' > ' + selectedArea.name :
                                    selectedFactory.name}
                    </p>
                </div>
            )}

            {/* Inline Create Dialog */}
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                <DialogContent className="sm:max-w-[400px]">
                    <DialogHeader>
                        <DialogTitle>
                            Criar {getTypeLabel(createType)}
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <p className="text-sm text-slate-500">
                            Será criado(a) em: <span className="font-medium text-slate-700">{createParent?.name}</span>
                        </p>
                        <div className="space-y-2">
                            <Label>Nome *</Label>
                            <Input
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                placeholder={`Nome da ${getTypeLabel(createType)}`}
                                autoFocus
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Código (Opcional)</Label>
                            <Input
                                value={newCode}
                                onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                                placeholder="Ex: A1, L02"
                                maxLength={10}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                            Cancelar
                        </Button>
                        <Button onClick={handleCreate} disabled={creating}>
                            {creating ? 'Criando...' : 'Criar'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
