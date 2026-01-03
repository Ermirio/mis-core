import { useState, useEffect } from 'react'
import api from '../services/api'
import {
  Plus,
  Edit,
  Trash2,
  Cpu,
  MapPin,
  Zap,
  Activity,
  Settings,
  CheckCircle,
  AlertCircle,
  Play,
  Network,
  Database,
  ArrowRight,
  ChevronRight,
  Gauge,
  Package,
  Filter,
  X,
  Factory,
  Map,
  Layout,
  Server,
  BarChart2
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Checkbox } from '@/components/ui/checkbox'
import { useToast } from '@/hooks/use-toast'
import { HierarchyManager } from './HierarchyManager'
import { HierarchySelector } from './HierarchySelector'
import { EquipmentMetricsPanel } from './EquipmentMetricsPanel'

export function Equipments() {
  const [equipments, setEquipments] = useState([])
  const [gateways, setGateways] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingEquipment, setEditingEquipment] = useState(null)
  const [activeTab, setActiveTab] = useState('basic')
  const { toast } = useToast()

  // Real-time values state
  const [realTimeValues, setRealTimeValues] = useState({}) // {equipmentId: {value, unit, timestamp}}
  const [refreshingRealTime, setRefreshingRealTime] = useState(false)

  // Metrics panel state
  const [metricsEquipment, setMetricsEquipment] = useState(null)

  // Filter states
  const [hierarchyData, setHierarchyData] = useState([])
  const [filters, setFilters] = useState({
    factory: 'all',
    area: 'all',
    line: 'all',
    machine_group: 'all',
    search: ''
  })

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    hierarchy_id: null,
    hierarchy_path: '',
    meter_type: 'energy',
    equipment_type: 'generic',
    parameters: {},
    standard_consumption: '',
    gateway_id: '',
    modbus_address: '',
    opc_node_id: '',
    // Multi-metric OPC addresses
    opc_node_power_kw: '',
    opc_node_energy_kwh: '',
    opc_node_demand_kw: '',
    opc_node_power_factor: '',
    opc_node_voltage_a: '',
    opc_node_voltage_b: '',
    opc_node_voltage_c: '',
    opc_node_current_a: '',
    opc_node_current_b: '',
    opc_node_current_c: '',
    // Cost configuration
    // Cost configuration
    tariff_kwh: 0.5,
    tariff_demand: '',
    modbus_register: '',
    register_type: 'holding',
    data_type: 'float32',
    scale_factor: 1.0,
    unit: 'kWh',
    is_active: true,
    is_entry_point: false,
    polling_interval: 60,
    // Production Fields (stored in parameters but helpful here for form bind)
    production_total_node: '',
    production_rate_node: '',
    production_sku_node: '',
    production_format_node: ''
  })

  useEffect(() => {
    fetchEquipments()
    fetchGateways()
    fetchHierarchy()
  }, [])

  const fetchEquipments = async () => {
    try {
      const data = await api.get('/equipments')
      if (data.success) {
        setEquipments(data.data)
      }
    } catch (error) {
      console.error('Erro ao carregar equipamentos:', error)
      toast({
        title: 'Erro',
        description: 'Não foi possível carregar a lista de equipamentos.',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }

  // Fetch real-time values for visible equipment
  const fetchRealTimeValues = async () => {
    if (equipments.length === 0) return

    setRefreshingRealTime(true)
    try {
      const updates = await Promise.all(
        equipments.slice(0, 20).map(async (eq) => { // Limit to first 20 to avoid overload
          try {
            const data = await api.post(`/equipments/${eq.id}/read`, {}, { timeout: 10000 })
            if (data.success) {
              return { id: eq.id, value: data.data.value, unit: data.data.unit, timestamp: new Date(), success: true }
            }
            return { id: eq.id, success: false }
          } catch {
            return { id: eq.id, success: false }
          }
        })
      )

      const newValues = {}
      updates.forEach(u => {
        if (u.success) {
          newValues[u.id] = { value: u.value, unit: u.unit, timestamp: u.timestamp }
        }
      })
      setRealTimeValues(prev => ({ ...prev, ...newValues }))
    } catch (error) {
      console.error("Error fetching real-time values:", error)
    } finally {
      setRefreshingRealTime(false)
    }
  }

  // Auto-refresh real-time values every 10 seconds
  useEffect(() => {
    if (equipments.length > 0) {
      fetchRealTimeValues() // Initial fetch
    }
    const interval = setInterval(() => {
      if (!loading && equipments.length > 0) {
        fetchRealTimeValues()
      }
    }, 10000)
    return () => clearInterval(interval)
  }, [equipments.length])

  const fetchGateways = async () => {
    try {
      const data = await api.get('/gateways')
      if (data.success) {
        setGateways(data.data.filter(g => g.is_active))
      }
    } catch (error) {
      console.error('Erro ao carregar gateways:', error)
    }
  }

  const fetchHierarchy = async () => {
    try {
      const data = await api.get('/hierarchy/tree')
      if (data.success) {
        setHierarchyData(data.data)
      }
    } catch (error) {
      console.error('Erro ao carregar hierarquia:', error)
    }
  }

  // Helper functions to get filter options based on hierarchy
  const getFactories = () => hierarchyData.filter(h => h.type === 'factory')
  const getAreas = (factoryId) => {
    if (!factoryId) return []
    const factory = hierarchyData.find(h => h.id.toString() === factoryId)
    return factory?.children?.filter(c => c.type === 'area') || []
  }
  const getLines = (areaId) => {
    if (!areaId) return []
    for (const factory of hierarchyData) {
      const area = factory.children?.find(c => c.id.toString() === areaId)
      if (area) return area.children?.filter(c => c.type === 'line') || []
    }
    return []
  }
  const getMachineGroups = (lineId) => {
    if (!lineId) return []
    for (const factory of hierarchyData) {
      for (const area of factory.children || []) {
        const line = area.children?.find(c => c.id.toString() === lineId)
        if (line) return line.children?.filter(c => c.type === 'machine_group') || []
      }
    }
    return []
  }

  // Get all child hierarchy IDs recursively
  const getAllChildIds = (parentId, data) => {
    const result = [parentId]
    const findChildren = (nodes, targetId) => {
      for (const node of nodes) {
        if (node.parent_id === targetId || node.id === targetId) {
          result.push(node.id)
        }
        if (node.children && node.children.length > 0) {
          findChildren(node.children, targetId)
        }
      }
    }

    // Flatten hierarchy for easier searching
    const flattenHierarchy = (nodes) => {
      let flat = []
      for (const node of nodes) {
        flat.push({ id: node.id, parent_id: node.parent_id })
        if (node.children) {
          flat = flat.concat(flattenHierarchy(node.children))
        }
      }
      return flat
    }

    const flat = flattenHierarchy(data)
    // Find all descendants
    const findDescendants = (id) => {
      const children = flat.filter(n => n.parent_id === parseInt(id))
      for (const child of children) {
        if (!result.includes(child.id)) {
          result.push(child.id)
          findDescendants(child.id)
        }
      }
    }
    findDescendants(parentId)
    return result
  }

  // Filter equipments based on selected hierarchy (with recursive children)
  const filteredEquipments = equipments.filter(eq => {
    // Text search filter
    if (filters.search && !eq.name.toLowerCase().includes(filters.search.toLowerCase())) {
      return false
    }
    // Hierarchy filter - get selected ID and include all children recursively
    const selectedId =
      (filters.machine_group && filters.machine_group !== 'all' ? filters.machine_group : null) ||
      (filters.line && filters.line !== 'all' ? filters.line : null) ||
      (filters.area && filters.area !== 'all' ? filters.area : null) ||
      (filters.factory && filters.factory !== 'all' ? filters.factory : null)

    if (selectedId) {
      // Get all child hierarchy IDs recursively and check if equipment belongs to any
      const childIds = getAllChildIds(parseInt(selectedId), hierarchyData)
      return childIds.includes(eq.hierarchy_id)
    }
    return true
  })

  const clearFilters = () => {
    setFilters({ factory: 'all', area: 'all', line: 'all', machine_group: 'all', search: '' })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    try {


      const payload = {
        ...formData,
        standard_consumption: formData.standard_consumption ? parseFloat(formData.standard_consumption) : null,
        scale_factor: parseFloat(formData.scale_factor),
        polling_interval: parseInt(formData.polling_interval),
        parameters: {
          ...formData.parameters,
          // Add Production Nodes to parameters JSON
          production_total_node: formData.production_total_node,
          production_rate_node: formData.production_rate_node,
          production_sku_node: formData.production_sku_node,
          production_format_node: formData.production_format_node
        }
      }

      // Parse numeric fields based on gateway protocol
      const selectedGateway = gateways.find(g => g.id.toString() === formData.gateway_id)
      if (selectedGateway && selectedGateway.protocol_type === 'modbus') {
        payload.gateway_id = parseInt(formData.gateway_id)
        payload.modbus_address = parseInt(formData.modbus_address)
        payload.modbus_register = parseInt(formData.modbus_register)
      } else if (selectedGateway) {
        payload.gateway_id = parseInt(formData.gateway_id)
      }

      const url = editingEquipment ? `/equipments/${editingEquipment.id}` : '/equipments'

      let data;
      if (editingEquipment) {
        data = await api.put(url, payload);
      } else {
        data = await api.post(url, payload);
      }

      if (data.success) {
        toast({
          title: editingEquipment ? 'Equipamento atualizado' : 'Equipamento criado',
          description: 'Operação realizada com sucesso.',
        })

        setDialogOpen(false)
        resetForm()
        fetchEquipments()
      } else {
        toast({
          title: 'Erro',
          description: data.error || 'Erro ao salvar equipamento.',
          variant: 'destructive',
        })
      }
    } catch (error) {
      console.error("Erro ao salvar equipamento:", error);
      toast({
        title: 'Erro',
        description: 'Erro ao salvar equipamento.',
        variant: 'destructive',
      })
    }
  }

  const handleEdit = (equipment) => {
    setEditingEquipment(equipment)
    setFormData({
      name: equipment.name,
      description: equipment.description || '',
      hierarchy_id: equipment.hierarchy_id,
      hierarchy_path: equipment.hierarchy_path || '',
      meter_type: equipment.meter_type || 'energy',
      equipment_type: equipment.equipment_type || 'generic',
      parameters: equipment.parameters || {},
      standard_consumption: equipment.standard_consumption || '',
      gateway_id: equipment.gateway_id ? equipment.gateway_id.toString() : '',
      modbus_address: equipment.modbus_address ? equipment.modbus_address.toString() : '',
      opc_node_id: equipment.opc_node_id || '',
      // Multi-metric OPC addresses
      opc_node_power_kw: equipment.opc_node_power_kw || '',
      opc_node_energy_kwh: equipment.opc_node_energy_kwh || '',
      opc_node_demand_kw: equipment.opc_node_demand_kw || '',
      opc_node_power_factor: equipment.opc_node_power_factor || '',
      opc_node_voltage_a: equipment.opc_node_voltage_a || '',
      opc_node_voltage_b: equipment.opc_node_voltage_b || '',
      opc_node_voltage_c: equipment.opc_node_voltage_c || '',
      opc_node_current_a: equipment.opc_node_current_a || '',
      opc_node_current_b: equipment.opc_node_current_b || '',
      opc_node_current_c: equipment.opc_node_current_c || '',
      // Cost configuration
      tariff_kwh: equipment.tariff_kwh || 0.5,
      tariff_demand: equipment.tariff_demand || '',
      modbus_register: equipment.modbus_register ? equipment.modbus_register.toString() : '',
      register_type: equipment.register_type,
      data_type: equipment.data_type,
      scale_factor: equipment.scale_factor,
      unit: equipment.unit,
      is_active: equipment.is_active,
      is_entry_point: equipment.is_entry_point || false,
      is_entry_point: equipment.is_entry_point || false,
      polling_interval: equipment.polling_interval,
      // Load Production Params
      production_total_node: equipment.parameters?.production_total_node || '',
      production_rate_node: equipment.parameters?.production_rate_node || '',
      production_sku_node: equipment.parameters?.production_sku_node || '',
      production_format_node: equipment.parameters?.production_format_node || ''
    })
    setDialogOpen(true)
  }

  const handleDelete = async (id) => {
    console.log('[Equipments] Tentando excluir equipamento ID:', id);
    if (!confirm('Tem certeza que deseja excluir este equipamento?')) {
      console.log('[Equipments] Exclusão cancelada pelo usuário.');
      return;
    }

    try {
      console.log('[Equipments] Enviando requisição DELETE para /equipments/' + id);
      const data = await api.delete(`/equipments/${id}`)
      console.log('[Equipments] Resposta DELETE:', data);

      if (data.success) {
        toast({
          title: 'Equipamento excluído',
          description: 'Equipamento excluído com sucesso.',
        })
        fetchEquipments()
      } else {
        toast({
          title: 'Erro',
          description: data.error || 'Erro ao excluir equipamento.',
          variant: 'destructive',
        })
      }
    } catch (error) {
      console.error("Erro ao excluir equipamento:", error);
      toast({
        title: 'Erro',
        description: 'Erro ao excluir equipamento.',
        variant: 'destructive',
      })
    }
  }

  const readEquipmentValue = async (equipment) => {
    try {
      const data = await api.post(`/equipments/${equipment.id}/read`, {}, { timeout: 30000 })

      if (data.success) {
        toast({
          title: 'Leitura realizada',
          description: `Valor atual: ${data.data.value} ${data.data.unit}`,
        })
      } else {
        toast({
          title: 'Erro na leitura',
          description: data.data?.error || data.error || 'Não foi possível ler o valor do equipamento.',
          variant: 'destructive',
        })
      }
    } catch (error) {
      console.error("Erro ao ler valor:", error)
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao realizar leitura.'
      toast({
        title: 'Erro',
        description: errorMsg,
        variant: 'destructive',
      })
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      hierarchy_id: null,
      hierarchy_path: '',
      meter_type: 'energy',
      equipment_type: 'generic',
      parameters: {},
      standard_consumption: '',
      gateway_id: '',
      modbus_address: '',
      opc_node_id: '',
      modbus_register: '',
      register_type: 'holding',
      data_type: 'float32',
      scale_factor: 1.0,
      unit: 'kWh',
      is_active: true,
      is_entry_point: false,
      is_entry_point: false,
      polling_interval: 60,
      production_total_node: '',
      production_rate_node: '',
      production_sku_node: '',
      production_format_node: ''
    })
    setEditingEquipment(null)
    setActiveTab('basic')
  }

  const updateParameter = (key, value) => {
    setFormData(prev => ({
      ...prev,
      parameters: {
        ...prev.parameters,
        [key]: value
      }
    }))
  }

  // Compact Equipment Card for 6-column grid with real-time value
  const EquipmentCard = ({ equipment, onDelete, onRead, onEdit, onViewMetrics }) => {
    // Get real-time value from state
    const rtValue = realTimeValues[equipment.id]
    const currentValue = rtValue?.value ?? equipment.last_value
    const displayUnit = rtValue?.unit || equipment.unit || 'kWh'

    // Check if above standard consumption
    const standardConsumption = equipment.standard_consumption
    const isAboveStandard = standardConsumption && currentValue > standardConsumption
    const consumptionPercent = standardConsumption ? (currentValue / standardConsumption) * 100 : null

    return (
      <Card className="group hover:shadow-md transition-all duration-200 cursor-pointer relative overflow-hidden">
        <CardContent className="p-3">
          {/* Header with icon and status */}
          <div className="flex items-center justify-between mb-2">
            <div className={`p-1.5 rounded-md ${equipment.meter_type === 'energy'
              ? 'bg-blue-100 dark:bg-blue-900/30'
              : 'bg-green-100 dark:bg-green-900/30'
              }`}>
              {equipment.meter_type === 'energy' ? (
                <Zap className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              ) : (
                <Package className="h-4 w-4 text-green-600 dark:text-green-400" />
              )}
            </div>
            <Badge
              variant={equipment.is_active ? 'default' : 'secondary'}
              className={`text-[10px] px-1.5 py-0.5 ${equipment.is_active ? 'bg-green-500' : ''}`}
            >
              {equipment.is_active ? 'On' : 'Off'}
            </Badge>
          </div>

          {/* Name - truncated */}
          <h4 className="font-medium text-sm text-slate-900 dark:text-white truncate" title={equipment.name}>
            {equipment.name}
          </h4>

          {/* Location - small */}
          <p className="text-[11px] text-slate-500 truncate mt-0.5" title={equipment.hierarchy_path}>
            {equipment.hierarchy_path || 'Sem local'}
          </p>

          {/* Real-time Value Display */}
          <div className={`mt-2 p-2 rounded-md ${isAboveStandard
            ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
            : 'bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700'
            }`}>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500">
                {equipment.meter_type === 'energy' ? 'Potência' : 'Vazão'}
              </span>
              {rtValue && (
                <span className="text-[10px] text-slate-400">
                  {rtValue.timestamp?.toLocaleTimeString().slice(0, 5)}
                </span>
              )}
            </div>
            <p className={`text-lg font-bold ${isAboveStandard ? 'text-red-600' : 'text-slate-900 dark:text-white'}`}>
              {currentValue != null ? Number(currentValue).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) : '--'}
              <span className="text-xs font-normal ml-1">{displayUnit}</span>
            </p>
          </div>
          
          {/* Financial Metrics - Only for energy meters */}
          {equipment.meter_type === 'energy' && equipment.tariff_kwh && currentValue != null && (
            <div className="mt-2 p-2 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-500">Custo/Hora</span>
                <span className="text-xs font-bold text-amber-700 dark:text-amber-400">
                  R$ {(currentValue * (equipment.tariff_kwh || 0.5)).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          )}
          
          {/* Gateway Info */}
          <div className="mt-2 flex items-center gap-1 text-[10px] text-slate-400">
            <Network className="h-3 w-3" />
            <span className="truncate">{equipment.gateway?.name || 'Sem gateway'}</span>
          </div>

          {/* Consumption Progress Bar */}
          {consumptionPercent !== null && (
            <div className="mt-2">
              <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
                <span>Padrão: {standardConsumption}</span>
                <span className={isAboveStandard ? 'text-red-500 font-medium' : 'text-green-500'}>
                  {consumptionPercent.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${consumptionPercent > 100 ? 'bg-red-500' : 'bg-green-500'}`}
                  style={{ width: `${Math.min(consumptionPercent, 100)}%` }}
                />
              </div>
            </div>
          )}
        </CardContent>

        {/* Hover actions overlay */}
        <div className="absolute inset-0 bg-white/95 dark:bg-slate-900/95 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => { e.stopPropagation(); onViewMetrics(equipment); }}
            className="h-8 px-2 bg-blue-50 hover:bg-blue-100 text-blue-600"
            title="Ver Métricas"
          >
            <BarChart2 className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => { e.stopPropagation(); onRead(equipment); }}
            className="h-8 px-2"
            title="Ler Valor"
          >
            <Activity className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => { e.stopPropagation(); onEdit(equipment); }}
            className="h-8 px-2"
            title="Editar"
          >
            <Edit className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => { e.stopPropagation(); onDelete(equipment.id); }}
            className="h-8 px-2 text-red-600 hover:text-red-700"
            title="Excluir"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </Card>
    )
  }

  if (loading) {
    return <div className="p-8 text-center">Carregando equipamentos...</div>
  }

  return (
    <div className="space-y-6">
      <style>{`
        @media (min-width: 768px) { .md\\:grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
        @media (min-width: 1024px) { .lg\\:grid-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
        @media (min-width: 1280px) { .xl\\:grid-cols-6 { grid-template-columns: repeat(6, minmax(0, 1fr)); } }
      `}</style>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Equipamentos</h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Gerenciar equipamentos de medição de energia
          </p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={resetForm} className="flex items-center space-x-2">
              <Plus className="h-4 w-4" />
              <span>Novo Equipamento</span>
            </Button>
          </DialogTrigger>

          <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingEquipment ? 'Editar Equipamento' : 'Novo Equipamento'}
              </DialogTitle>
              <DialogDescription>
                Configure as informações do equipamento de medição.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="basic">Básico & Local</TabsTrigger>
                  <TabsTrigger value="type">Tipo & Parâmetros</TabsTrigger>
                  <TabsTrigger value="addressing">Endereçamento</TabsTrigger>
                </TabsList>

                <TabsContent value="basic" className="space-y-4 py-4">
                  {/* Meter Type Selector */}
                  <div className="space-y-2">
                    <Label>Tipo de Medidor</Label>
                    <div className="grid grid-cols-2 gap-4">
                      <div
                        className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${formData.meter_type === 'energy'
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-slate-200 hover:border-slate-300'
                          }`}
                        onClick={() => setFormData({ ...formData, meter_type: 'energy', unit: 'kWh' })}
                      >
                        <div className="flex items-center gap-3">
                          <Zap className={`h-6 w-6 ${formData.meter_type === 'energy' ? 'text-blue-500' : 'text-slate-400'}`} />
                          <div>
                            <p className="font-medium">Medidor de Energia</p>
                            <p className="text-xs text-slate-500">Mede consumo em kWh</p>
                          </div>
                        </div>
                      </div>
                      <div
                        className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${formData.meter_type === 'production'
                          ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                          : 'border-slate-200 hover:border-slate-300'
                          }`}
                        onClick={() => setFormData({ ...formData, meter_type: 'production', unit: 'ton' })}
                      >
                        <div className="flex items-center gap-3">
                          <Package className={`h-6 w-6 ${formData.meter_type === 'production' ? 'text-green-500' : 'text-slate-400'}`} />
                          <div>
                            <p className="font-medium">Medidor de Produção</p>
                            <p className="text-xs text-slate-500">Mede produção em ton/kg</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Nome do Equipamento</Label>
                    <Input
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="Ex: Motor Principal A1"
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Descrição</Label>
                    <Textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Descrição opcional"
                      rows={2}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Localização na Fábrica</Label>
                    <div className="border rounded-md p-2 bg-slate-50 dark:bg-slate-900">
                      <HierarchySelector
                        selectedId={formData.hierarchy_id}
                        onSelect={(node) => setFormData({
                          ...formData,
                          hierarchy_id: node.id,
                          hierarchy_path: node.name // Simplificado para exibição
                        })}
                      />
                    </div>
                    {formData.hierarchy_path && (
                      <p className="text-sm text-green-600 mt-1">
                        Selecionado: {formData.hierarchy_path}
                      </p>
                    )}
                  </div>


                  {/* Input Meter Checkbox - Hide for Production */}
                  {formData.meter_type !== 'production' && (
                    <div className="flex items-center space-x-2 border p-3 rounded-md bg-slate-50 dark:bg-slate-900/50 mt-4">
                      <Checkbox
                        id="is_entry_point"
                        checked={formData.is_entry_point}
                        onCheckedChange={(checked) => setFormData({ ...formData, is_entry_point: checked })}
                      />
                      <div className="grid gap-1.5 leading-none">
                        <label
                          htmlFor="is_entry_point"
                          className="text-sm font-medium leading-none"
                        >
                          É Medidor de Entrada?
                        </label>
                        <p className="text-xs text-slate-500">
                          Totalizador principal hierárquico.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Gateway Selection moved to Addressing tab */}
                  <p className="text-sm text-slate-500 pt-4 border-t">
                    Selecione o Gateway na aba "Endereçamento" para configurar a comunicação.
                  </p>
                </TabsContent>

                <TabsContent value="type" className="space-y-4 py-4">
                  {/* Tipo de Equipamento - diferente para Energia vs Produção */}
                  {formData.meter_type === 'energy' ? (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Tipo de Equipamento</Label>
                        <Select
                          value={formData.equipment_type}
                          onValueChange={(value) => setFormData({ ...formData, equipment_type: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="generic">Genérico</SelectItem>
                            <SelectItem value="motor">Motor</SelectItem>
                            <SelectItem value="resistor">Resistência</SelectItem>
                            <SelectItem value="lighting">Iluminação</SelectItem>
                            <SelectItem value="compressor">Compressor</SelectItem>
                            <SelectItem value="energy_meter">Medidor de Energia</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label>Consumo Padrão (referência)</Label>
                        <div className="flex space-x-2">
                          <Input
                            type="number"
                            step="0.01"
                            value={formData.standard_consumption}
                            onChange={(e) => setFormData({ ...formData, standard_consumption: e.target.value })}
                            placeholder="100.5"
                          />
                          <Select
                            value={formData.unit}
                            onValueChange={(value) => setFormData({ ...formData, unit: value })}
                          >
                            <SelectTrigger className="w-[100px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="kWh">kWh</SelectItem>
                              <SelectItem value="kW">kW</SelectItem>
                              <SelectItem value="A">A</SelectItem>
                              <SelectItem value="V">V</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <p className="text-xs text-slate-500">
                          Usado para identificar consumo acima do esperado
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Tipo de Medidor de Produção</Label>
                        <Select
                          value={formData.equipment_type}
                          onValueChange={(value) => setFormData({ ...formData, equipment_type: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="production_meter">Medidor de Produção</SelectItem>
                            <SelectItem value="counter">Contador</SelectItem>
                            <SelectItem value="scale">Balança</SelectItem>
                            <SelectItem value="flow_meter">Medidor de Vazão</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label>Produção Padrão (meta/referência)</Label>
                        <div className="flex space-x-2">
                          <Input
                            type="number"
                            step="0.01"
                            value={formData.standard_consumption}
                            onChange={(e) => setFormData({ ...formData, standard_consumption: e.target.value })}
                            placeholder="50.0"
                          />
                          <Select
                            value={formData.unit}
                            onValueChange={(value) => setFormData({ ...formData, unit: value })}
                          >
                            <SelectTrigger className="w-[100px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ton">ton</SelectItem>
                              <SelectItem value="kg">kg</SelectItem>
                              <SelectItem value="pieces">peças</SelectItem>
                              <SelectItem value="m3">m³</SelectItem>
                              <SelectItem value="L">L</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <p className="text-xs text-slate-500">
                          Usado para identificar produção abaixo do esperado
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Dynamic Parameters based on Type */}
                  {formData.equipment_type === 'motor' && (
                    <div className="grid grid-cols-2 gap-4 border-t pt-4">
                      <div className="space-y-2">
                        <Label>RPM Nominal</Label>
                        <Input
                          type="number"
                          value={formData.parameters.rpm || ''}
                          onChange={(e) => updateParameter('rpm', e.target.value)}
                          placeholder="1750"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Potência (CV/HP)</Label>
                        <Input
                          type="number"
                          value={formData.parameters.power_cv || ''}
                          onChange={(e) => updateParameter('power_cv', e.target.value)}
                          placeholder="10"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Eficiência (%)</Label>
                        <Input
                          type="number"
                          value={formData.parameters.efficiency || ''}
                          onChange={(e) => updateParameter('efficiency', e.target.value)}
                          placeholder="92.5"
                        />
                      </div>
                    </div>
                  )}

                  {formData.equipment_type === 'resistor' && (
                    <div className="grid grid-cols-2 gap-4 border-t pt-4">
                      <div className="space-y-2">
                        <Label>Resistência (Ohms)</Label>
                        <Input
                          type="number"
                          value={formData.parameters.resistance || ''}
                          onChange={(e) => updateParameter('resistance', e.target.value)}
                        />
                      </div>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="addressing" className="space-y-4 py-4">
                  {/* Gateway Selection */}
                  <div className="space-y-2">
                    <Label>Gateway / Servidor</Label>
                    <Select
                      value={formData.gateway_id}
                      onValueChange={(value) => setFormData({ ...formData, gateway_id: value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selecione um Gateway..." />
                      </SelectTrigger>
                      <SelectContent>
                        {gateways.map((gateway) => (
                          <SelectItem key={gateway.id} value={gateway.id.toString()}>
                            <span className="flex items-center space-x-2">
                              <span className="uppercase text-xs bg-slate-200 px-1 rounded">{gateway.protocol_type || 'modbus'}</span>
                              <span>{gateway.name}</span>
                              <span className="text-slate-500">({gateway.protocol_type === 'opc' ? gateway.opc_url : gateway.ip_address})</span>
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {formData.gateway_id && (() => {
                    const selectedGateway = gateways.find(g => g.id.toString() === formData.gateway_id)
                    if (!selectedGateway) return null

                    if (selectedGateway.protocol_type === 'opc') {
                      return (
                        <div className="space-y-4 border rounded-md p-4 bg-purple-50/50 dark:bg-purple-900/10">
                          <p className="text-sm text-purple-700 dark:text-purple-300 font-medium">Configuração OPC UA - Multi-Métricas</p>

                          {/* Métricas Principais (Condicionais por tipo) */}
                          <div className="space-y-3">
                            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                              {formData.meter_type === 'production' ? 'Métricas de Produção' : 'Métricas de Energia'}
                            </p>

                            {formData.meter_type === 'production' ? (
                              /* PRODUCTION FIELDS */
                              <div className="grid grid-cols-1 gap-3">
                                <div className="space-y-1.5">
                                  <Label className="flex items-center gap-2 text-sm">
                                    <span className="text-lg">📦</span> Totalizador Produção
                                  </Label>
                                  <Input
                                    value={formData.production_total_node}
                                    onChange={(e) => setFormData({ ...formData, production_total_node: e.target.value })}
                                    placeholder="ns=2;s=Line.Production_Total"
                                    className="font-mono text-sm"
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <Label className="flex items-center gap-2 text-sm">
                                    <span className="text-lg">⏱️</span> Vazão/Velocidade (Hora)
                                  </Label>
                                  <Input
                                    value={formData.production_rate_node}
                                    onChange={(e) => setFormData({ ...formData, production_rate_node: e.target.value })}
                                    placeholder="ns=2;s=Line.Speed_UnitsPerHour"
                                    className="font-mono text-sm"
                                  />
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                  <div className="space-y-1.5">
                                    <Label className="flex items-center gap-2 text-sm">
                                      <span className="text-lg">🏷️</span> SKU (Tags)
                                    </Label>
                                    <Input
                                      value={formData.production_sku_node}
                                      onChange={(e) => setFormData({ ...formData, production_sku_node: e.target.value })}
                                      placeholder="ns=2;s=Line.CurrentSKU"
                                      className="font-mono text-sm"
                                    />
                                  </div>
                                  <div className="space-y-1.5">
                                    <Label className="flex items-center gap-2 text-sm">
                                      <span className="text-lg">📐</span> Formato
                                    </Label>
                                    <Input
                                      value={formData.production_format_node}
                                      onChange={(e) => setFormData({ ...formData, production_format_node: e.target.value })}
                                      placeholder="ns=2;s=Line.CurrentFormat"
                                      className="font-mono text-sm"
                                    />
                                  </div>
                                </div>
                              </div>
                            ) : (
                              /* ENERGY FIELDS */
                              <div className="grid grid-cols-1 gap-3">
                                <div className="space-y-1.5">
                                  <Label className="flex items-center gap-2 text-sm">
                                    <span className="text-lg">⚡</span> Potência Ativa (kW)
                                  </Label>
                                  <Input
                                    value={formData.opc_node_power_kw}
                                    onChange={(e) => setFormData({ ...formData, opc_node_power_kw: e.target.value })}
                                    placeholder="ns=2;s=Meter.Power_kW"
                                    className="font-mono text-sm"
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <Label className="flex items-center gap-2 text-sm">
                                    <span className="text-lg">📊</span> Energia Acumulada (kWh)
                                  </Label>
                                  <Input
                                    value={formData.opc_node_energy_kwh}
                                    onChange={(e) => setFormData({ ...formData, opc_node_energy_kwh: e.target.value })}
                                    placeholder="ns=2;s=Meter.Energy_kWh"
                                    className="font-mono text-sm"
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <Label className="flex items-center gap-2 text-sm">
                                    <span className="text-lg">📈</span> Demanda Máxima (kW)
                                  </Label>
                                  <Input
                                    value={formData.opc_node_demand_kw}
                                    onChange={(e) => setFormData({ ...formData, opc_node_demand_kw: e.target.value })}
                                    placeholder="ns=2;s=Meter.Demand_kW"
                                    className="font-mono text-sm"
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <Label className="flex items-center gap-2 text-sm">
                                    <span className="text-lg">🎯</span> Fator de Potência
                                  </Label>
                                  <Input
                                    value={formData.opc_node_power_factor}
                                    onChange={(e) => setFormData({ ...formData, opc_node_power_factor: e.target.value })}
                                    placeholder="ns=2;s=Meter.PowerFactor"
                                    className="font-mono text-sm"
                                  />
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Qualidade de Energia - Hide for Production */}
                          {formData.meter_type !== 'production' && (
                            <div className="space-y-3 pt-3 border-t border-purple-200">
                              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Qualidade de Energia (Opcional)</p>

                              {/* Tensão por Fase */}
                              <div className="space-y-2">
                                <Label className="text-xs text-slate-500">Tensão por Fase (V)</Label>
                                <div className="grid grid-cols-3 gap-2">
                                  <div>
                                    <Input
                                      value={formData.opc_node_voltage_a}
                                      onChange={(e) => setFormData({ ...formData, opc_node_voltage_a: e.target.value })}
                                      placeholder="Fase A"
                                      className="font-mono text-xs"
                                    />
                                  </div>
                                  <div>
                                    <Input
                                      value={formData.opc_node_voltage_b}
                                      onChange={(e) => setFormData({ ...formData, opc_node_voltage_b: e.target.value })}
                                      placeholder="Fase B"
                                      className="font-mono text-xs"
                                    />
                                  </div>
                                  <div>
                                    <Input
                                      value={formData.opc_node_voltage_c}
                                      onChange={(e) => setFormData({ ...formData, opc_node_voltage_c: e.target.value })}
                                      placeholder="Fase C"
                                      className="font-mono text-xs"
                                    />
                                  </div>
                                </div>
                              </div>

                              {/* Corrente por Fase */}
                              <div className="space-y-2">
                                <Label className="text-xs text-slate-500">Corrente por Fase (A)</Label>
                                <div className="grid grid-cols-3 gap-2">
                                  <div>
                                    <Input
                                      value={formData.opc_node_current_a}
                                      onChange={(e) => setFormData({ ...formData, opc_node_current_a: e.target.value })}
                                      placeholder="Fase A"
                                      className="font-mono text-xs"
                                    />
                                  </div>
                                  <div>
                                    <Input
                                      value={formData.opc_node_current_b}
                                      onChange={(e) => setFormData({ ...formData, opc_node_current_b: e.target.value })}
                                      placeholder="Fase B"
                                      className="font-mono text-xs"
                                    />
                                  </div>
                                  <div>
                                    <Input
                                      value={formData.opc_node_current_c}
                                      onChange={(e) => setFormData({ ...formData, opc_node_current_c: e.target.value })}
                                      placeholder="Fase C"
                                      className="font-mono text-xs"
                                    />
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Configuração de Custo - Hide for Production */}
                          {formData.meter_type !== 'production' && (
                            <div className="space-y-3 pt-3 border-t border-purple-200">
                              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Configuração de Custo</p>
                              <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1.5">
                                  <Label className="text-sm">Tarifa (R$/kWh)</Label>
                                  <Input
                                    type="number"
                                    step="0.01"
                                    value={formData.tariff_kwh}
                                    onChange={(e) => setFormData({ ...formData, tariff_kwh: e.target.value })}
                                    placeholder="0.50"
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <Label className="text-sm">Tarifa Demanda (R$/kW)</Label>
                                  <Input
                                    type="number"
                                    step="0.01"
                                    value={formData.tariff_demand}
                                    onChange={(e) => setFormData({ ...formData, tariff_demand: e.target.value })}
                                    placeholder="25.00"
                                  />
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Legacy NodeID (compatibilidade) */}
                          <div className="space-y-2 pt-3 border-t border-dashed border-slate-300">
                            <Label className="text-xs text-slate-400">NodeID Legado (compatibilidade)</Label>
                            <Input
                              value={formData.opc_node_id}
                              onChange={(e) => setFormData({ ...formData, opc_node_id: e.target.value })}
                              placeholder="ns=2;s=Machine1.Power"
                              className="font-mono text-xs opacity-60"
                            />
                          </div>
                        </div>
                      )
                    } else {
                      return (
                        <div className="space-y-4 border rounded-md p-4 bg-blue-50/50 dark:bg-blue-900/10">
                          <p className="text-sm text-blue-700 dark:text-blue-300 font-medium">Configuração Modbus TCP</p>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label>Endereço Slave</Label>
                              <Input
                                type="number"
                                value={formData.modbus_address}
                                onChange={(e) => setFormData({ ...formData, modbus_address: e.target.value })}
                                placeholder="1"
                              />
                            </div>
                            <div className="space-y-2">
                              <Label>Registro (Endereço de Memória)</Label>
                              <Input
                                type="number"
                                value={formData.modbus_register}
                                onChange={(e) => setFormData({ ...formData, modbus_register: e.target.value })}
                                placeholder="40001"
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <Label>Tipo de Registro</Label>
                            <Select
                              value={formData.register_type}
                              onValueChange={(value) => setFormData({ ...formData, register_type: value })}
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="holding">Holding Register</SelectItem>
                                <SelectItem value="input">Input Register</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      )
                    }
                  })()}

                  <div className="grid grid-cols-3 gap-4 mt-4">
                    <div className="space-y-2">
                      <Label>Tipo de Dados</Label>
                      <Select
                        value={formData.data_type}
                        onValueChange={(value) => setFormData({ ...formData, data_type: value })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="float32">Float 32</SelectItem>
                          <SelectItem value="int16">Int 16</SelectItem>
                          <SelectItem value="int32">Int 32</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Fator de Escala</Label>
                      <Input
                        type="number"
                        step="0.001"
                        value={formData.scale_factor}
                        onChange={(e) => setFormData({ ...formData, scale_factor: e.target.value })}
                        placeholder="1.0"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Intervalo (s)</Label>
                      <Input
                        type="number"
                        value={formData.polling_interval}
                        onChange={(e) => setFormData({ ...formData, polling_interval: e.target.value })}
                        placeholder="60"
                      />
                    </div>
                  </div>
                </TabsContent>
              </Tabs>

              <div className="flex justify-end space-x-2 pt-4 border-t mt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDialogOpen(false)}
                >
                  Cancelar
                </Button>
                <Button type="submit">
                  {editingEquipment ? 'Atualizar' : 'Criar'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filter Bar */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
            <Filter className="h-4 w-4" />
            Filtrar:
          </div>

          {/* Factory Filter */}
          <Select
            value={filters.factory}
            onValueChange={(value) => setFilters({ ...filters, factory: value, area: 'all', line: 'all', machine_group: 'all' })}
          >
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <Factory className="h-3 w-3 mr-1" />
              <SelectValue placeholder="Fábrica" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {getFactories().map(f => (
                <SelectItem key={f.id} value={f.id.toString()}>{f.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Area Filter */}
          <Select
            value={filters.area}
            onValueChange={(value) => setFilters({ ...filters, area: value, line: 'all', machine_group: 'all' })}
            disabled={filters.factory === 'all'}
          >
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <Map className="h-3 w-3 mr-1" />
              <SelectValue placeholder="Área" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {getAreas(filters.factory).map(a => (
                <SelectItem key={a.id} value={a.id.toString()}>{a.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Line Filter */}
          <Select
            value={filters.line}
            onValueChange={(value) => setFilters({ ...filters, line: value, machine_group: 'all' })}
            disabled={filters.area === 'all'}
          >
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <Layout className="h-3 w-3 mr-1" />
              <SelectValue placeholder="Linha" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {getLines(filters.area).map(l => (
                <SelectItem key={l.id} value={l.id.toString()}>{l.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Machine Group Filter */}
          <Select
            value={filters.machine_group}
            onValueChange={(value) => setFilters({ ...filters, machine_group: value })}
            disabled={filters.line === 'all'}
          >
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <Server className="h-3 w-3 mr-1" />
              <SelectValue placeholder="Grupo" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              {getMachineGroups(filters.line).map(g => (
                <SelectItem key={g.id} value={g.id.toString()}>{g.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Search */}
          <Input
            placeholder="Buscar..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="w-[150px] h-8 text-xs"
          />

          {/* Clear Filters */}
          {(filters.factory !== 'all' || filters.search) && (
            <Button variant="ghost" size="sm" onClick={clearFilters} className="h-8 px-2">
              <X className="h-4 w-4 mr-1" />
              Limpar
            </Button>
          )}

          {/* Results count */}
          <span className="text-xs text-slate-500 ml-auto">
            {filteredEquipments.length} de {equipments.length} equipamentos
          </span>
        </div>
      </Card>

      {/* Equipments Grid - 6 columns */}
      {
        filteredEquipments.length === 0 ? (
          <Card className="text-center py-12">
            <CardContent>
              <Cpu className="h-12 w-12 text-slate-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                {equipments.length === 0 ? 'Nenhum equipamento configurado' : 'Nenhum equipamento encontrado'}
              </h3>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                {equipments.length === 0
                  ? 'Adicione seu primeiro equipamento para começar o monitoramento.'
                  : 'Tente ajustar os filtros para ver mais resultados.'}
              </p>
              {equipments.length === 0 && (
                <Button onClick={() => setDialogOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Adicionar Equipamento
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
            {filteredEquipments.map((equipment) => (
              <EquipmentCard
                key={equipment.id}
                equipment={equipment}
                onDelete={handleDelete}
                onRead={readEquipmentValue}
                onEdit={handleEdit}
                onViewMetrics={setMetricsEquipment}
              />
            ))}
          </div>
        )
      }

      {/* Equipment Metrics Panel */}
      {
        metricsEquipment && (
          <EquipmentMetricsPanel
            equipment={metricsEquipment}
            onClose={() => setMetricsEquipment(null)}
          />
        )
      }
    </div >
  )
}
