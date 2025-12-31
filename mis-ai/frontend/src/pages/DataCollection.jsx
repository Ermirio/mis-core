import { useState, useEffect } from 'react'
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardFooter, // Importado para a paginação
  CardHeader, 
  CardTitle 
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Calendar } from '@/components/ui/calendar'
import { 
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { 
  Database, 
  Plus, 
  Calendar as CalendarIcon, 
  Clock,
  AlertCircle,
  CheckCircle,
  Save
} from 'lucide-react'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

const DataCollection = ({ selectedLine, selectedTarget }) => {
  // --- Estados do Componente ---
  const [data, setData] = useState([])
  const [opcLogs, setOpcLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [logDialogOpen, setLogDialogOpen] = useState(false)
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [formData, setFormData] = useState({
    measured_value: '',
    timestamp: new Date().toISOString().slice(0, 16)
  })
  const [selectedLogTimestamp, setSelectedLogTimestamp] = useState(null)
  
  // --- Estados para a Paginação ---
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(15) // Você pode ajustar este número

  const { toast } = useToast()

  // --- Efeitos (Lifecycle) ---
  useEffect(() => {
    if (selectedTarget) {
      loadData()
    } else {
      setData([]) // Limpa a tabela se nenhum target estiver selecionado
    }
  }, [selectedTarget])

  useEffect(() => {
    if (logDialogOpen) {
      loadOpcLogs()
    }
  }, [logDialogOpen, selectedDate, selectedLine])

  // --- Funções de Carregamento de Dados ---
  const loadData = async () => {
    if (!selectedTarget) return
    
    try {
      const endTime = new Date()
      const startTime = new Date(endTime.getTime() - 7 * 24 * 60 * 60 * 1000) // 7 dias atrás
      
      const resultData = await api.getData({
        target_id: selectedTarget.id,
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        data_type: 'prediction'
      })
      setData(resultData)
      setCurrentPage(1) // Reseta para a primeira página ao carregar novos dados
    } catch (error) {
      toast({
        title: "Erro ao carregar dados",
        description: error.message || "Não foi possível buscar os dados da API.",
        variant: "destructive"
      })
    }
  }

  const loadOpcLogs = async () => {
    if (!selectedLine || !selectedDate) return
    
    try {
      const dateStr = format(selectedDate, 'yyyy-MM-dd')
      const logs = await api.getOPCLogsByDate(selectedLine, dateStr)
      setOpcLogs(logs)
    } catch (error) {
      console.error('Erro ao carregar logs OPC:', error)
      toast({
        title: "Erro ao buscar logs",
        description: "Não foi possível carregar os logs OPC para a data selecionada.",
        variant: "destructive"
      })
      setOpcLogs([])
    }
  }

  // --- Funções de Submissão de Formulários ---
  const handleManualSubmit = async (e) => {
    e.preventDefault()
    if (!formData.measured_value.trim()) {
      toast({
        title: "Campo obrigatório",
        description: "O campo 'Valor medido' não pode estar vazio.",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      await api.saveManualData({
        target_id: selectedTarget.id,
        measured_value: parseFloat(formData.measured_value),
        timestamp: formData.timestamp
      })
      toast({
        title: "Sucesso!",
        description: "Dados manuais foram salvos."
      })
      setDialogOpen(false)
      setFormData({
        measured_value: '',
        timestamp: new Date().toISOString().slice(0, 16)
      })
      loadData() // Recarrega os dados para exibir o novo item
    } catch (error) {
      toast({
        title: "Erro ao salvar",
        description: error.message || "Ocorreu um problema ao salvar os dados.",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleOpcSubmit = async (e) => {
    e.preventDefault()
    if (!formData.measured_value.trim() || !selectedLogTimestamp) {
      toast({
        title: "Dados incompletos",
        description: "É necessário preencher o valor medido e selecionar um log OPC.",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      await api.saveManualData({
        target_id: selectedTarget.id,
        measured_value: parseFloat(formData.measured_value),
        log_timestamp: selectedLogTimestamp
      })
      toast({
        title: "Sucesso!",
        description: "Dados associados ao log OPC com sucesso."
      })
      setLogDialogOpen(false)
      setFormData({
        measured_value: '',
        timestamp: new Date().toISOString().slice(0, 16)
      })
      setSelectedLogTimestamp(null)
      loadData() // Recarrega os dados para exibir o novo item
    } catch (error) {
      toast({
        title: "Erro ao associar",
        description: error.message || "Ocorreu um problema ao salvar os dados.",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  // --- Funções Utilitárias ---
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Data inválida'
    return new Date(timestamp).toLocaleString('pt-BR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    })
  }

  const formatValue = (value, decimals = 4) => {
    if (value === null || value === undefined) return 'N/A'
    return typeof value === 'number' ? value.toFixed(decimals) : String(value)
  }

  // --- Lógica da Paginação ---
  const indexOfLastItem = currentPage * itemsPerPage
  const indexOfFirstItem = indexOfLastItem - itemsPerPage
  const currentItems = data.slice(indexOfFirstItem, indexOfLastItem)
  const totalPages = Math.ceil(data.length / itemsPerPage)

  const handlePageChange = (pageNumber) => {
    // Garante que não saia dos limites de páginas existentes
    if (pageNumber >= 1 && pageNumber <= totalPages) {
      setCurrentPage(pageNumber)
    }
  }

  // --- Renderização Condicional (Early Return) ---
  if (!selectedTarget) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Coleta de Dados</h1>
          <p className="text-muted-foreground">
            Colete dados para treinamento dos modelos
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center text-center py-12">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-2">Nenhum Target Selecionado</h3>
            <p className="text-muted-foreground">
              Por favor, selecione um target na barra de navegação para visualizar e coletar dados.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  // --- Renderização Principal ---
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Coleta de Dados</h1>
          <p className="text-muted-foreground">
            Coletando dados para <strong>{selectedTarget.target_name}</strong> na linha <strong>{selectedLine}</strong>
          </p>
        </div>
        
        <div className="flex space-x-2">
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="flex items-center space-x-2 transition-all duration-200 hover:scale-105 hover:shadow-lg hover:bg-gray-50 dark:hover:bg-gray-800 border-2 hover:border-gray-300 dark:hover:border-gray-600">
                <Plus className="h-4 w-4 transition-transform duration-200 hover:rotate-90" />
                <span>Dados Manuais</span>
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Adicionar Dados Manuais</DialogTitle>
                <DialogDescription>
                  Insira dados coletados manualmente para o target {selectedTarget.target_name}.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleManualSubmit}>
                <div className="space-y-4 py-4">
                  <div>
                    <Label htmlFor="measured_value">
                      Valor Medido ({selectedTarget.target_unit || 'unidade'}) *
                    </Label>
                    <Input
                      id="measured_value"
                      type="number"
                      step="any"
                      value={formData.measured_value}
                      onChange={(e) => setFormData(prev => ({ ...prev, measured_value: e.target.value }))}
                      placeholder="Digite o valor medido..."
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="timestamp">Timestamp</Label>
                    <Input
                      id="timestamp"
                      type="datetime-local"
                      value={formData.timestamp}
                      onChange={(e) => setFormData(prev => ({ ...prev, timestamp: e.target.value }))}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" disabled={loading} className="bg-blue-600 text-white hover:bg-blue-700">
                    {loading ? 'Salvando...' : 'Salvar Dados'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          <Dialog open={logDialogOpen} onOpenChange={setLogDialogOpen}>
            <DialogTrigger asChild>
              <Button className="flex items-center space-x-2 bg-blue-600 text-white hover:bg-blue-700">
                <Database className="h-4 w-4" />
                <span>Associar com OPC</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Associar com Logs OPC</DialogTitle>
                <DialogDescription>
                  Associe um valor medido com logs OPC existentes para este target.
                </DialogDescription>
              </DialogHeader>
              
              <Tabs defaultValue="select-date" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="select-date">1. Selecionar Log</TabsTrigger>
                  <TabsTrigger value="enter-data" disabled={!selectedLogTimestamp}>2. Inserir Dados</TabsTrigger>
                </TabsList>
                
                <TabsContent value="select-date" className="space-y-4">
                  <div>
                    <Label>Data dos Logs OPC</Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" className="w-full justify-start text-left font-normal">
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {selectedDate ? format(selectedDate, 'PPP', { locale: ptBR }) : 'Selecione uma data'}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0">
                        <Calendar mode="single" selected={selectedDate} onSelect={setSelectedDate} initialFocus />
                      </PopoverContent>
                    </Popover>
                  </div>
                  
                  <div>
                    <Label>Logs Disponíveis</Label>
                    <div className="max-h-60 overflow-y-auto border rounded-md">
                      {opcLogs.length > 0 ? (
                        <div className="p-2 space-y-1">
                          {opcLogs.map((timestamp) => (
                            <Button
                              key={timestamp}
                              variant={selectedLogTimestamp === timestamp ? "default" : "ghost"}
                              size="sm"
                              className="w-full justify-start"
                              onClick={() => setSelectedLogTimestamp(timestamp)}
                            >
                              <Clock className="h-4 w-4 mr-2" />
                              <span className="font-medium">{formatTimestamp(timestamp)}</span>
                            </Button>
                          ))}
                        </div>
                      ) : (
                        <div className="p-8 text-center text-muted-foreground">
                          <Database className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p>Nenhum log encontrado para esta data.</p>
                        </div>
                      )}
                    </div>
                  </div>
                </TabsContent>
                
                <TabsContent value="enter-data" className="space-y-4">
                  <form onSubmit={handleOpcSubmit}>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="opc_measured_value">
                          Valor Medido ({selectedTarget.target_unit || 'unidade'}) *
                        </Label>
                        <Input
                          id="opc_measured_value"
                          type="number"
                          step="any"
                          value={formData.measured_value}
                          onChange={(e) => setFormData(prev => ({ ...prev, measured_value: e.target.value }))}
                          placeholder="Digite o valor medido..."
                          required
                        />
                      </div>
                      
                      {selectedLogTimestamp && (
                        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-700">
                          <div className="flex items-center space-x-2">
                            <CheckCircle className="h-5 w-5 text-green-500" />
                            <span className="text-sm font-semibold text-green-800 dark:text-green-300">Log OPC Selecionado:</span>
                          </div>
                          <p className="text-sm font-mono text-gray-700 dark:text-gray-300 mt-1 ml-7">
                            {formatTimestamp(selectedLogTimestamp)}
                          </p>
                        </div>
                      )}
                    </div>
                    
                    <DialogFooter className="mt-6">
                      <Button type="button" variant="outline" onClick={() => setLogDialogOpen(false)}>
                        Cancelar
                      </Button>
                      <Button type="submit" disabled={loading || !selectedLogTimestamp} className="bg-green-600 text-white hover:bg-green-700">
                        <Save className="h-4 w-4 mr-2" />
                        {loading ? 'Salvando...' : 'Salvar e Associar'}
                      </Button>
                    </DialogFooter>
                  </form>
                </TabsContent>
              </Tabs>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Tabela de Dados */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Database className="h-5 w-5" />
            <span>Dados Coletados</span>
          </CardTitle>
          <CardDescription>
            Histórico de dados coletados para treinamento do modelo.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2 font-semibold">ID</th>
                    <th className="text-left p-2 font-semibold">Valor Medido</th>
                    <th className="text-left p-2 font-semibold">Valor Predito</th>
                    <th className="text-left p-2 font-semibold">Fonte</th>
                    <th className="text-left p-2 font-semibold">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Mapeia sobre os itens da página atual */}
                  {currentItems.map((item) => (
                    <tr key={item.id} className="border-b last:border-b-0 hover:bg-muted/50">
                      <td className="p-2 font-mono text-xs">{item.id}</td>
                      <td className="p-2">
                        {item.measured_value ? (
                          <span className="font-medium">
                            {formatValue(item.measured_value)} {selectedTarget.target_unit}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">N/A</span>
                        )}
                      </td>
                      <td className="p-2">
                        {item.predicted_value ? (
                          <span className="text-blue-600">
                            {formatValue(item.predicted_value)} {selectedTarget.target_unit}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">N/A</span>
                        )}
                      </td>
                      <td className="p-2">
                        <Badge variant={item.data_source === 'manual' ? 'default' : 'secondary'}>
                          {item.data_source === 'manual' ? 'Manual' : 'OPC'}
                        </Badge>
                      </td>
                      <td className="p-2 text-muted-foreground text-xs font-mono">
                        {formatTimestamp(item.timestamp)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
    _          </div>
          ) : (
            <div className="text-center py-12">
              <Database className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-semibold mb-2">Nenhum dado encontrado</h3>
              <p className="text-muted-foreground mb-4">
                Comece a coletar dados para treinar seus modelos ou verifique os filtros.
              </p>
            </div>
          )}
        </CardContent>
        {/* Controles de Paginação */}
        {totalPages > 1 && (
          <CardFooter>
            <div className="flex w-full items-center justify-between text-xs text-muted-foreground">
              <span className="font-semibold">
                Mostrando {indexOfFirstItem + 1} - {Math.min(indexOfLastItem, data.length)} de {data.length} registros
              </span>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  Anterior
                </Button>
                <span className="font-semibold">
                  Página {currentPage} de {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                >
                  Próximo
                </Button>
              </div>
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  )
}

export default DataCollection