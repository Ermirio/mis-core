import { useState, useEffect } from 'react'
import api from '../services/api'
import {
  Plus,
  Edit,
  Trash2,
  Wifi,
  WifiOff,
  Router,
  Settings,
  CheckCircle,
  AlertCircle,
  Network,
  Database
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { useToast } from '@/hooks/use-toast'

export function Gateways() {
  const [gateways, setGateways] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingGateway, setEditingGateway] = useState(null)
  const { toast } = useToast()

  // Test Connection State
  const [testDialogOpen, setTestDialogOpen] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)

  const handleTestNewConnection = async () => {
    // Validar campos mínimos antes de testar
    if (formData.protocol_type === 'modbus' && !formData.ip_address) {
      toast({ title: 'Atenção', description: 'Informe o IP para testar.', variant: 'warning' })
      return
    }
    if (formData.protocol_type === 'opc' && !formData.opc_url) {
      toast({ title: 'Atenção', description: 'Informe a URL OPC para testar.', variant: 'warning' })
      return
    }

    setTestDialogOpen(true)
    setTestResult({ loading: true })
    setIsTesting(true)

    try {
      // Timeout de 30s para dar tempo ao backend tentar conectar (que pode ter timeout interno de 5-10s)
      const response = await api.post('/gateways/validate-connection', formData, { timeout: 30000 })

      if (response.success) {
        setTestResult({
          success: true,
          message: response.data?.message || 'Conexão realizada com sucesso!',
          data: response
        })
      } else {
        // Caso o backend retorne success: false mas sem throwing error
        setTestResult({
          success: false,
          error: response.error || response.data?.message || 'Falha desconhecida.'
        })
      }

    } catch (error) {
      console.error("Erro no teste:", error)
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao conectar com o servidor.'
      setTestResult({
        success: false,
        error: errorMsg
      })
    } finally {
      setIsTesting(false)
    }
  }

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    protocol_type: 'modbus',
    ip_address: '',
    port: 502,
    opc_url: '',
    security_mode: 'None',
    timeout: 5
  })

  useEffect(() => {
    fetchGateways()
  }, [])

  const fetchGateways = async () => {
    try {
      const data = await api.get('/gateways')
      if (data.success) {
        setGateways(data.data)
      }
    } catch (error) {
      console.error('Erro ao carregar gateways:', error)
      toast({
        title: 'Erro',
        description: 'Erro ao carregar lista de gateways.',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    try {
      const url = editingGateway ? `/gateways/${editingGateway.id}` : '/gateways'

      let data;
      if (editingGateway) {
        data = await api.put(url, formData);
      } else {
        data = await api.post(url, formData);
      }

      if (data.success) {
        toast({
          title: editingGateway ? 'Gateway atualizado' : 'Gateway criado',
          description: 'Operação realizada com sucesso.',
        })

        setDialogOpen(false)
        resetForm()
        fetchGateways()
      }
    } catch (error) {
      console.error("Erro ao salvar gateway:", error);
      // Toast já tratado se catch global ou pode adicionar específico aqui
      toast({
        title: 'Erro',
        description: 'Erro ao salvar gateway.',
        variant: 'destructive',
      })
    }
  }

  const handleEdit = (gateway) => {
    setEditingGateway(gateway)
    setFormData({
      name: gateway.name,
      description: gateway.description || '',
      protocol_type: gateway.protocol_type || 'modbus',
      ip_address: gateway.ip_address || '',
      port: gateway.port || 502,
      opc_url: gateway.opc_url || '',
      security_mode: gateway.security_mode || 'None',
      timeout: gateway.timeout || 5
    })
    setDialogOpen(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Tem certeza que deseja excluir este gateway?')) return

    try {
      const data = await api.delete(`/gateways/${id}`)

      if (data.success) {
        toast({
          title: 'Gateway excluído',
          description: 'Gateway excluído com sucesso.',
        })
        fetchGateways()
      }
    } catch (error) {
      console.error("Erro ao excluir gateway:", error);
      toast({
        title: 'Erro',
        description: 'Erro ao excluir gateway.',
        variant: 'destructive',
      })
    }
  }

  const testConnection = async (gateway) => {
    setTestDialogOpen(true)
    setTestResult({ loading: true })

    try {
      const data = await api.post(`/gateways/${gateway.id}/test`, {}, { timeout: 30000 })

      if (data.success) {
        setTestResult({
          success: true,
          message: data.data?.message || 'Conexão realizada com sucesso!',
          data: data
        })
      } else {
        setTestResult({
          success: false,
          error: data.data?.error || data.error || 'Falha na conexão.'
        })
      }
    } catch (error) {
      console.error("Erro ao testar gateway:", error)
      const errorMsg = error.response?.data?.error || error.response?.data?.data?.error || error.message || 'Erro ao conectar com o servidor.'
      setTestResult({
        success: false,
        error: errorMsg
      })
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      protocol_type: 'modbus',
      ip_address: '',
      port: 502,
      opc_url: '',
      security_mode: 'None',
      timeout: 5
    })
    setEditingGateway(null)
  }

  const GatewayCard = ({ gateway }) => (
    <Card className="hover:shadow-lg transition-shadow duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${gateway.protocol_type === 'opc' ? 'bg-purple-100 dark:bg-purple-900/20' : 'bg-blue-100 dark:bg-blue-900/20'}`}>
              {gateway.protocol_type === 'opc' ? (
                <Database className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              ) : (
                <Network className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              )}
            </div>
            <div>
              <CardTitle className="text-lg">{gateway.name}</CardTitle>
              <CardDescription>{gateway.description}</CardDescription>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="uppercase">
              {gateway.protocol_type || 'modbus'}
            </Badge>
            <Badge
              variant={gateway.is_active ? 'default' : 'secondary'}
              className="flex items-center space-x-1"
            >
              {gateway.is_active ? (
                <CheckCircle className="h-3 w-3" />
              ) : (
                <AlertCircle className="h-3 w-3" />
              )}
              <span>{gateway.is_active ? 'Ativo' : 'Inativo'}</span>
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          {gateway.protocol_type === 'opc' ? (
            <>
              <div className="col-span-2">
                <span className="text-slate-500 dark:text-slate-400">URL OPC UA:</span>
                <p className="font-medium font-mono text-xs">{gateway.opc_url || 'N/A'}</p>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400">Segurança:</span>
                <p className="font-medium">{gateway.security_mode || 'None'}</p>
              </div>
            </>
          ) : (
            <>
              <div>
                <span className="text-slate-500 dark:text-slate-400">IP:</span>
                <p className="font-medium">{gateway.ip_address}</p>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400">Porta:</span>
                <p className="font-medium">{gateway.port}</p>
              </div>
            </>
          )}
          <div>
            <span className="text-slate-500 dark:text-slate-400">Timeout:</span>
            <p className="font-medium">{gateway.timeout}s</p>
          </div>
          <div>
            <span className="text-slate-500 dark:text-slate-400">Equipamentos:</span>
            <p className="font-medium">{gateway.equipment_count || 0}</p>
          </div>
        </div>

        <div className="flex items-center space-x-2 pt-2 border-t">
          <Button
            variant="outline"
            size="sm"
            onClick={() => testConnection(gateway)}
            className="flex-1"
          >
            <Wifi className="h-4 w-4 mr-2" />
            Testar
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleEdit(gateway)}
          >
            <Edit className="h-4 w-4" />
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleDelete(gateway)}
            className="text-red-600 hover:text-red-700"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-6 bg-slate-200 rounded w-3/4"></div>
                <div className="h-4 bg-slate-200 rounded w-1/2"></div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="h-4 bg-slate-200 rounded"></div>
                  <div className="h-4 bg-slate-200 rounded w-2/3"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Gateways</h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Gerenciar gateways de comunicação (Modbus TCP ou OPC UA)
          </p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={resetForm} className="flex items-center space-x-2">
              <Plus className="h-4 w-4" />
              <span>Novo Gateway</span>
            </Button>
          </DialogTrigger>

          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>
                {editingGateway ? 'Editar Gateway' : 'Novo Gateway'}
              </DialogTitle>
              <DialogDescription>
                Configure as informações de conexão do gateway.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Protocol Type Selection */}
              <div className="space-y-2">
                <Label>Tipo de Protocolo</Label>
                <div className="grid grid-cols-2 gap-4">
                  <div
                    className={`cursor-pointer border-2 rounded-lg p-4 flex flex-col items-center justify-center space-y-2 transition-all ${formData.protocol_type === 'modbus' ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-slate-200 hover:border-slate-300'}`}
                    onClick={() => setFormData({ ...formData, protocol_type: 'modbus' })}
                  >
                    <Network className={`h-8 w-8 ${formData.protocol_type === 'modbus' ? 'text-blue-500' : 'text-slate-400'}`} />
                    <span className="font-medium">Modbus TCP</span>
                  </div>
                  <div
                    className={`cursor-pointer border-2 rounded-lg p-4 flex flex-col items-center justify-center space-y-2 transition-all ${formData.protocol_type === 'opc' ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20' : 'border-slate-200 hover:border-slate-300'}`}
                    onClick={() => setFormData({ ...formData, protocol_type: 'opc' })}
                  >
                    <Database className={`h-8 w-8 ${formData.protocol_type === 'opc' ? 'text-purple-500' : 'text-slate-400'}`} />
                    <span className="font-medium">OPC UA</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Nome</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Ex: Gateway Principal"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Descrição</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Descrição opcional do gateway"
                  rows={2}
                />
              </div>

              {/* Modbus TCP Fields */}
              {formData.protocol_type === 'modbus' && (
                <div className="space-y-4 border rounded-md p-4 bg-blue-50/50 dark:bg-blue-900/10">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="ip_address">Endereço IP</Label>
                      <Input
                        id="ip_address"
                        value={formData.ip_address}
                        onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                        placeholder="192.168.1.100"
                        required
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="port">Porta</Label>
                      <Input
                        id="port"
                        type="number"
                        value={formData.port}
                        onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) })}
                        placeholder="502"
                        required
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* OPC UA Fields */}
              {formData.protocol_type === 'opc' && (
                <div className="space-y-4 border rounded-md p-4 bg-purple-50/50 dark:bg-purple-900/10">
                  <div className="space-y-2">
                    <Label htmlFor="opc_url">URL do Servidor OPC UA</Label>
                    <Input
                      id="opc_url"
                      value={formData.opc_url}
                      onChange={(e) => setFormData({ ...formData, opc_url: e.target.value })}
                      placeholder="opc.tcp://192.168.1.100:4840"
                      required
                    />
                    <p className="text-xs text-slate-500">
                      Formato: opc.tcp://[ip]:[porta]/[endpoint]
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="security_mode">Modo de Segurança</Label>
                    <Select
                      value={formData.security_mode}
                      onValueChange={(value) => setFormData({ ...formData, security_mode: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="None">None (Sem criptografia)</SelectItem>
                        <SelectItem value="Sign">Sign (Assinado)</SelectItem>
                        <SelectItem value="SignAndEncrypt">Sign & Encrypt (Assinado e Criptografado)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="timeout">Timeout (segundos)</Label>
                <Input
                  id="timeout"
                  type="number"
                  value={formData.timeout}
                  onChange={(e) => setFormData({ ...formData, timeout: parseInt(e.target.value) })}
                  placeholder="5"
                  required
                />
              </div>

              <div className="flex justify-between items-center pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleTestNewConnection}
                  disabled={isTesting}
                >
                  {isTesting ? (
                    'Testando...'
                  ) : (
                    <>
                      <Wifi className="h-4 w-4 mr-2" />
                      Testar Conexão
                    </>
                  )}
                </Button>

                <div className="flex space-x-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setDialogOpen(false)}
                  >
                    Cancelar
                  </Button>
                  <Button type="submit">
                    {editingGateway ? 'Atualizar' : 'Criar'}
                  </Button>
                </div>
              </div>
            </form>
          </DialogContent>
        </Dialog>

        {/* Test Result Dialog */}
        <Dialog open={testDialogOpen} onOpenChange={setTestDialogOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {testResult?.success ? (
                  <CheckCircle className="h-6 w-6 text-green-500" />
                ) : (
                  <AlertCircle className="h-6 w-6 text-red-500" />
                )}
                Resultado do Teste de Conexão
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {testResult?.loading ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                  <p className="mt-4 text-sm text-muted-foreground">Tentando conectar ao dispositivo...</p>
                </div>
              ) : (
                <div className={`p-4 rounded-md border ${testResult?.success ? 'bg-green-50 border-green-200 dark:bg-green-900/20' : 'bg-red-50 border-red-200 dark:bg-red-900/20'}`}>
                  <h4 className={`font-medium mb-1 ${testResult?.success ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                    {testResult?.success ? 'Conexão Estabelecida!' : 'Falha na Conexão'}
                  </h4>
                  <p className="text-sm opacity-90 break-words mb-2">
                    {testResult?.message || testResult?.error || 'Sem detalhes.'}
                  </p>

                  {/* Detalhes Técnicos se for erro */}
                  {!testResult?.success && testResult?.error && (
                    <div className="mt-2 text-xs font-mono bg-black/5 p-2 rounded overflow-auto max-h-[100px]">
                      {String(testResult.error)}
                    </div>
                  )}

                  {/* Detalhes Técnicos se for sucesso */}
                  {testResult?.success && testResult?.data?.data && (
                    <div className="mt-2 text-xs space-y-1">
                      <p>Tempo de resposta: {testResult.data.data.details?.response_time || testResult.data.data.data?.response_time || 'N/A'}s</p>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="flex justify-end">
              <Button onClick={() => setTestDialogOpen(false)}>
                Fechar
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Gateways Grid */}
      {gateways.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <Router className="h-12 w-12 text-slate-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
              Nenhum gateway configurado
            </h3>
            <p className="text-slate-600 dark:text-slate-400 mb-4">
              Adicione seu primeiro gateway para começar a monitorar equipamentos.
            </p>
            <Button onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Adicionar Gateway
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {gateways.map((gateway) => (
            <GatewayCard key={gateway.id} gateway={gateway} />
          ))}
        </div>
      )}
    </div>
  )
}

