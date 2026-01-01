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
  ChevronRight
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
import { useToast } from '@/hooks/use-toast'
import { HierarchyManager } from './HierarchyManager'
import { HierarchySelector } from './HierarchySelector'

export function Equipments() {
  const [equipments, setEquipments] = useState([])
  const [gateways, setGateways] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingEquipment, setEditingEquipment] = useState(null)
  const [activeTab, setActiveTab] = useState('basic')
  const { toast } = useToast()

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    hierarchy_id: null,
    hierarchy_path: '',
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
    polling_interval: 60
  })

  useEffect(() => {
    fetchEquipments()
    fetchGateways()
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

  const handleSubmit = async (e) => {
    e.preventDefault()

    try {


      const payload = {
        ...formData,
        standard_consumption: formData.standard_consumption ? parseFloat(formData.standard_consumption) : null,
        scale_factor: parseFloat(formData.scale_factor),
        polling_interval: parseInt(formData.polling_interval)
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
      equipment_type: equipment.equipment_type || 'generic',
      parameters: equipment.parameters || {},
      standard_consumption: equipment.standard_consumption || '',
      gateway_id: equipment.gateway_id ? equipment.gateway_id.toString() : '',
      modbus_address: equipment.modbus_address ? equipment.modbus_address.toString() : '',
      opc_node_id: equipment.opc_node_id || '',
      modbus_register: equipment.modbus_register ? equipment.modbus_register.toString() : '',
      register_type: equipment.register_type,
      data_type: equipment.data_type,
      scale_factor: equipment.scale_factor,
      unit: equipment.unit,
      polling_interval: equipment.polling_interval
    })
    setDialogOpen(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Tem certeza que deseja excluir este equipamento?')) return

    try {
      const data = await api.delete(`/equipments/${id}`)

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
      const response = await fetch(`/api/equipments/${equipment.id}/read`, {
        method: 'POST',
      })

      const data = await response.json()

      if (data.success) {
        toast({
          title: 'Leitura realizada',
          description: `Valor atual: ${data.data.value} ${data.data.unit}`,
        })
      } else {
        toast({
          title: 'Erro na leitura',
          description: data.error || 'Não foi possível ler o valor do equipamento.',
          variant: 'destructive',
        })
      }
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Erro ao realizar leitura.',
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
      polling_interval: 60
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

  const EquipmentCard = ({ equipment }) => (
    <Card className="hover:shadow-lg transition-shadow duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-green-100 dark:bg-green-900/20 rounded-lg">
              <Cpu className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <CardTitle className="text-lg">{equipment.name}</CardTitle>
              <CardDescription>{equipment.hierarchy_path || 'Sem localização'}</CardDescription>
            </div>
          </div>

          <Badge
            variant={equipment.is_active ? 'default' : 'secondary'}
            className="flex items-center space-x-1"
          >
            {equipment.is_active ? (
              <CheckCircle className="h-3 w-3" />
            ) : (
              <AlertCircle className="h-3 w-3" />
            )}
            <span>{equipment.is_active ? 'Ativo' : 'Inativo'}</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-slate-500 dark:text-slate-400 flex items-center">
              <Settings className="h-3 w-3 mr-1" />
              Tipo:
            </span>
            <p className="font-medium capitalize">{equipment.equipment_type}</p>
          </div>
          <div>
            <span className="text-slate-500 dark:text-slate-400 flex items-center">
              <Network className="h-3 w-3 mr-1" />
              Protocolo:
            </span>
            <p className="font-medium uppercase">{equipment.address_type}</p>
          </div>
          <div>
            <span className="text-slate-500 dark:text-slate-400 flex items-center">
              <Zap className="h-3 w-3 mr-1" />
              Consumo Padrão:
            </span>
            <p className="font-medium">
              {equipment.standard_consumption ? `${equipment.standard_consumption} ${equipment.unit}` : 'N/A'}
            </p>
          </div>
          <div>
            <span className="text-slate-500 dark:text-slate-400">Endereço:</span>
            <p className="font-medium">
              {equipment.address_type === 'modbus'
                ? `Modbus: ${equipment.modbus_address}`
                : `NodeID: ${equipment.opc_node_id}`}
            </p>
          </div>
        </div>

        {equipment.last_value && (
          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600 dark:text-slate-400">Última Leitura:</span>
              <span className="font-bold text-lg text-green-600">
                {equipment.last_value} {equipment.unit}
              </span>
            </div>
            {equipment.last_reading_at && (
              <p className="text-xs text-slate-500 mt-1">
                {new Date(equipment.last_reading_at).toLocaleString()}
              </p>
            )}
          </div>
        )}

        <div className="flex items-center space-x-2 pt-2 border-t">
          <Button
            variant="outline"
            size="sm"
            onClick={() => readEquipmentValue(equipment)}
            className="flex-1"
          >
            <Activity className="h-4 w-4 mr-2" />
            Ler Valor
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleEdit(equipment)}
          >
            <Edit className="h-4 w-4" />
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleDelete(equipment)}
            className="text-red-600 hover:text-red-700"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )

  if (loading) {
    return <div className="p-8 text-center">Carregando equipamentos...</div>
  }

  return (
    <div className="space-y-6">
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

                  {/* Gateway Selection moved to Addressing tab */}
                  <p className="text-sm text-slate-500 pt-4 border-t">
                    Selecione o Gateway na aba "Endereçamento" para configurar a comunicação.
                  </p>
                </TabsContent>

                <TabsContent value="type" className="space-y-4 py-4">
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
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label>Consumo Padrão</Label>
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
                    </div>
                  </div>

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
                          <p className="text-sm text-purple-700 dark:text-purple-300 font-medium">Configuração OPC UA</p>
                          <div className="space-y-2">
                            <Label>NodeID (OPC UA)</Label>
                            <Input
                              value={formData.opc_node_id}
                              onChange={(e) => setFormData({ ...formData, opc_node_id: e.target.value })}
                              placeholder="ns=2;s=Machine1.Power"
                            />
                            <p className="text-xs text-slate-500">
                              Formato: ns=namespace;s=string_id ou ns=namespace;i=numeric_id
                            </p>
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

      {/* Equipments Grid */}
      {equipments.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <Cpu className="h-12 w-12 text-slate-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
              Nenhum equipamento configurado
            </h3>
            <p className="text-slate-600 dark:text-slate-400 mb-4">
              Adicione seu primeiro equipamento para começar o monitoramento.
            </p>
            <Button onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Adicionar Equipamento
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {equipments.map((equipment) => (
            <EquipmentCard key={equipment.id} equipment={equipment} />
          ))}
        </div>
      )}
    </div>
  )
}
