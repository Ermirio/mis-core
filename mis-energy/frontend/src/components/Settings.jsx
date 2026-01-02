import { useState, useEffect } from 'react'
import api from '../services/api'
import {
  Database,
  Server,
  CheckCircle,
  AlertCircle,
  Save,
  TestTube,
  Eye,
  EyeOff,
  DollarSign,
  Zap,
  ToggleLeft,
  ToggleRight,
  RefreshCw
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'

export function Settings() {
  const [mysqlConfig, setMysqlConfig] = useState({
    host: '',
    port: 3306,
    username: '',
    password: '',
    database: ''
  })

  const [influxConfig, setInfluxConfig] = useState({
    host: 'mis-core-influxdb',
    port: 8086,
    database: 'db_energy',
    username: '',
    password: ''
  })

  const [metricsConfig, setMetricsConfig] = useState({
    kwh_cost_brl: 0.85,
    usd_brl_rate: 5.0,
    eur_brl_rate: 5.5,
    production_unit: 'ton',
    production_unit_label: 'Toneladas',
    simulation_enabled: true
  })

  const [showMysqlPassword, setShowMysqlPassword] = useState(false)
  const [showInfluxToken, setShowInfluxToken] = useState(false)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState({ mysql: false, influx: false })
  const [savingMetrics, setSavingMetrics] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    fetchConfigs()
  }, [])

  const fetchConfigs = async () => {
    try {
      // Buscar configuração MySQL
      const mysqlData = await api.get('/config/mysql')
      if (mysqlData.success && mysqlData.data) {
        setMysqlConfig({ ...mysqlConfig, ...mysqlData.data })
      }

      // Buscar configuração InfluxDB
      const influxData = await api.get('/config/influxdb')
      if (influxData.success && influxData.data) {
        setInfluxConfig({ ...influxConfig, ...influxData.data })
      }

      // Buscar configuração de Métricas
      const metricsData = await api.get('/config/metrics')
      if (metricsData.success && metricsData.data) {
        setMetricsConfig({ ...metricsConfig, ...metricsData.data })
      }
    } catch (error) {
      console.error('Erro ao carregar configurações:', error)
    } finally {
      setLoading(false)
    }
  }

  const saveMetricsConfig = async () => {
    setSavingMetrics(true)
    try {
      const data = await api.put('/config/metrics', metricsConfig)
      if (data.success) {
        toast({
          title: 'Configurações de Métricas salvas',
          description: 'Configurações foram salvas com sucesso.',
        })
      }
    } catch (error) {
      console.error('Erro ao salvar config Métricas:', error)
      toast({
        title: 'Erro',
        description: 'Erro ao salvar configurações de métricas.',
        variant: 'destructive',
      })
    } finally {
      setSavingMetrics(false)
    }
  }

  const toggleSimulation = async () => {
    try {
      const data = await api.post('/config/simulation/toggle')
      if (data.success) {
        setMetricsConfig({ ...metricsConfig, simulation_enabled: data.data.simulation_enabled })
        toast({
          title: data.message,
          description: data.data.simulation_enabled ? 'Dados simulados serão usados.' : 'Dados reais do InfluxDB serão usados.',
        })
      }
    } catch (error) {
      console.error('Erro ao alternar simulação:', error)
    }
  }

  const saveMysqlConfig = async () => {
    try {
      const data = await api.post('/config/mysql', mysqlConfig)

      if (data.success) {
        toast({
          title: 'Configuração MySQL salva',
          description: 'Configurações do MySQL foram salvas com sucesso.',
        })
      }
    } catch (error) {
      console.error("Erro ao salvar config MySQL:", error);
      toast({
        title: 'Erro',
        description: 'Erro ao salvar configuração MySQL.',
        variant: 'destructive',
      })
    }
  }

  const saveInfluxConfig = async () => {
    try {
      const data = await api.post('/config/influxdb', influxConfig)

      if (data.success) {
        toast({
          title: 'Configuração InfluxDB salva',
          description: 'Configurações do InfluxDB foram salvas com sucesso.',
        })
      }
    } catch (error) {
      console.error("Erro ao salvar config InfluxDB:", error);
      toast({
        title: 'Erro',
        description: 'Erro ao salvar configuração InfluxDB.',
        variant: 'destructive',
      })
    }
  }

  const testMysqlConnection = async () => {
    setTesting({ ...testing, mysql: true })

    try {
      const data = await api.post('/config/mysql/test', mysqlConfig)

      if (data.success) {
        toast({
          title: 'Conexão MySQL bem-sucedida',
          description: data.data.message,
        })
      }
    } catch (error) {
      console.error("Erro ao testar MySQL:", error);
      toast({
        title: 'Falha na conexão MySQL',
        description: 'Não foi possível conectar ao MySQL.',
        variant: 'destructive',
      })
    } finally {
      setTesting({ ...testing, mysql: false })
    }
  }

  const testInfluxConnection = async () => {
    setTesting({ ...testing, influx: true })

    try {
      const data = await api.post('/config/influxdb/test', influxConfig)

      if (data.success) {
        toast({
          title: 'Conexão InfluxDB bem-sucedida',
          description: data.data.message,
        })
      }
    } catch (error) {
      console.error("Erro ao testar InfluxDB:", error);
      toast({
        title: 'Falha na conexão InfluxDB',
        description: 'Não foi possível conectar ao InfluxDB.',
        variant: 'destructive',
      })
    } finally {
      setTesting({ ...testing, influx: false })
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Card className="animate-pulse">
          <CardHeader>
            <div className="h-6 bg-slate-200 rounded w-1/4"></div>
            <div className="h-4 bg-slate-200 rounded w-1/2"></div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-10 bg-slate-200 rounded"></div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Configurações</h1>
        <p className="text-slate-600 dark:text-slate-400 mt-1">
          Configure as conexões com bancos de dados e outras configurações do sistema
        </p>
      </div>

      <Tabs defaultValue="metrics" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="metrics" className="flex items-center space-x-2">
            <DollarSign className="h-4 w-4" />
            <span>Métricas</span>
          </TabsTrigger>
          <TabsTrigger value="mysql" className="flex items-center space-x-2">
            <Database className="h-4 w-4" />
            <span>MySQL</span>
          </TabsTrigger>
          <TabsTrigger value="influxdb" className="flex items-center space-x-2">
            <Server className="h-4 w-4" />
            <span>InfluxDB</span>
          </TabsTrigger>
        </TabsList>

        {/* Metrics Configuration */}
        <TabsContent value="metrics">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center space-x-2">
                    <DollarSign className="h-5 w-5" />
                    <span>Configuração de Métricas</span>
                  </CardTitle>
                  <CardDescription>
                    Configure custos de energia, taxas de câmbio e unidades de produção
                  </CardDescription>
                </div>
                <Button
                  variant={metricsConfig.simulation_enabled ? "default" : "outline"}
                  onClick={toggleSimulation}
                  className="flex items-center space-x-2"
                >
                  {metricsConfig.simulation_enabled ? (
                    <><ToggleRight className="h-4 w-4" /><span>Simulação ATIVA</span></>
                  ) : (
                    <><ToggleLeft className="h-4 w-4" /><span>Dados Reais</span></>
                  )}
                </Button>
              </div>
            </CardHeader>

            <CardContent className="space-y-6">
              {/* Custo de Energia */}
              <div className="space-y-4">
                <h4 className="font-medium flex items-center gap-2">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  Custo de Energia
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="kwh-cost">Custo por kWh (R$)</Label>
                    <Input
                      id="kwh-cost"
                      type="number"
                      step="0.01"
                      value={metricsConfig.kwh_cost_brl}
                      onChange={(e) => setMetricsConfig({ ...metricsConfig, kwh_cost_brl: parseFloat(e.target.value) })}
                      placeholder="0.85"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="usd-rate">Cotação USD/BRL</Label>
                    <Input
                      id="usd-rate"
                      type="number"
                      step="0.01"
                      value={metricsConfig.usd_brl_rate}
                      onChange={(e) => setMetricsConfig({ ...metricsConfig, usd_brl_rate: parseFloat(e.target.value) })}
                      placeholder="5.00"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="eur-rate">Cotação EUR/BRL</Label>
                    <Input
                      id="eur-rate"
                      type="number"
                      step="0.01"
                      value={metricsConfig.eur_brl_rate}
                      onChange={(e) => setMetricsConfig({ ...metricsConfig, eur_brl_rate: parseFloat(e.target.value) })}
                      placeholder="5.50"
                    />
                  </div>
                </div>
              </div>

              {/* Unidade de Produção */}
              <div className="space-y-4">
                <h4 className="font-medium">Unidade de Produção</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Unidade</Label>
                    <Select
                      value={metricsConfig.production_unit}
                      onValueChange={(value) => {
                        const labels = { ton: 'Toneladas', kg: 'Quilogramas', pieces: 'Peças' }
                        setMetricsConfig({
                          ...metricsConfig,
                          production_unit: value,
                          production_unit_label: labels[value] || value
                        })
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ton">Toneladas (ton)</SelectItem>
                        <SelectItem value="kg">Quilogramas (kg)</SelectItem>
                        <SelectItem value="pieces">Peças (pcs)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="unit-label">Descrição da Unidade</Label>
                    <Input
                      id="unit-label"
                      value={metricsConfig.production_unit_label}
                      onChange={(e) => setMetricsConfig({ ...metricsConfig, production_unit_label: e.target.value })}
                      placeholder="Toneladas"
                    />
                  </div>
                </div>
              </div>

              {/* Info Box */}
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <h4 className="font-medium text-amber-900 dark:text-amber-100 mb-2">
                  Sobre o Modo de Simulação
                </h4>
                <ul className="text-sm text-amber-800 dark:text-amber-200 space-y-1">
                  <li>• <strong>Simulação ATIVA:</strong> Usa dados mockados para demonstração</li>
                  <li>• <strong>Dados Reais:</strong> Busca dados do InfluxDB (requer configuração)</li>
                  <li>• As métricas kWh/ton e R$/ton são calculadas automaticamente</li>
                </ul>
              </div>

              <div className="flex items-center space-x-4 pt-4 border-t">
                <Button onClick={saveMetricsConfig} disabled={savingMetrics} className="flex items-center space-x-2">
                  {savingMetrics ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  <span>{savingMetrics ? 'Salvando...' : 'Salvar Configuração'}</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* MySQL Configuration */}
        <TabsContent value="mysql">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center space-x-2">
                    <Database className="h-5 w-5" />
                    <span>Configuração MySQL</span>
                  </CardTitle>
                  <CardDescription>
                    Configure a conexão com o banco de dados MySQL para armazenar registros de equipamentos e gateways
                  </CardDescription>
                </div>
                <Badge variant="outline" className="flex items-center space-x-1">
                  <CheckCircle className="h-3 w-3 text-green-500" />
                  <span>Configurado</span>
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="mysql-host">Host</Label>
                  <Input
                    id="mysql-host"
                    value={mysqlConfig.host}
                    onChange={(e) => setMysqlConfig({ ...mysqlConfig, host: e.target.value })}
                    placeholder="localhost"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mysql-port">Porta</Label>
                  <Input
                    id="mysql-port"
                    type="number"
                    value={mysqlConfig.port}
                    onChange={(e) => setMysqlConfig({ ...mysqlConfig, port: parseInt(e.target.value) })}
                    placeholder="3306"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="mysql-database">Banco de Dados</Label>
                <Input
                  id="mysql-database"
                  value={mysqlConfig.database}
                  onChange={(e) => setMysqlConfig({ ...mysqlConfig, database: e.target.value })}
                  placeholder="energy_monitor"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="mysql-username">Usuário</Label>
                  <Input
                    id="mysql-username"
                    value={mysqlConfig.username}
                    onChange={(e) => setMysqlConfig({ ...mysqlConfig, username: e.target.value })}
                    placeholder="root"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mysql-password">Senha</Label>
                  <div className="relative">
                    <Input
                      id="mysql-password"
                      type={showMysqlPassword ? "text" : "password"}
                      value={mysqlConfig.password}
                      onChange={(e) => setMysqlConfig({ ...mysqlConfig, password: e.target.value })}
                      placeholder="••••••••"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                      onClick={() => setShowMysqlPassword(!showMysqlPassword)}
                    >
                      {showMysqlPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-4 pt-4 border-t">
                <Button onClick={saveMysqlConfig} className="flex items-center space-x-2">
                  <Save className="h-4 w-4" />
                  <span>Salvar Configuração</span>
                </Button>

                <Button
                  variant="outline"
                  onClick={testMysqlConnection}
                  disabled={testing.mysql}
                  className="flex items-center space-x-2"
                >
                  <TestTube className="h-4 w-4" />
                  <span>{testing.mysql ? 'Testando...' : 'Testar Conexão'}</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* InfluxDB Configuration */}
        <TabsContent value="influxdb">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center space-x-2">
                    <Server className="h-5 w-5" />
                    <span>Configuração InfluxDB 1.8</span>
                  </CardTitle>
                  <CardDescription>
                    Configure a conexão com o InfluxDB 1.8 para armazenar dados de medições (database padrão: db_energy)
                  </CardDescription>
                </div>
                <Badge variant="outline" className="flex items-center space-x-1">
                  <AlertCircle className="h-3 w-3 text-yellow-500" />
                  <span>1.8</span>
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="influx-host">Host</Label>
                  <Input
                    id="influx-host"
                    value={influxConfig.host}
                    onChange={(e) => setInfluxConfig({ ...influxConfig, host: e.target.value })}
                    placeholder="mis-core-influxdb"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="influx-port">Porta</Label>
                  <Input
                    id="influx-port"
                    type="number"
                    value={influxConfig.port}
                    onChange={(e) => setInfluxConfig({ ...influxConfig, port: parseInt(e.target.value) })}
                    placeholder="8086"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="influx-database">Database</Label>
                <Input
                  id="influx-database"
                  value={influxConfig.database}
                  onChange={(e) => setInfluxConfig({ ...influxConfig, database: e.target.value })}
                  placeholder="db_energy"
                />
                <p className="text-xs text-slate-500">Será criado automaticamente se não existir</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="influx-username">Usuário (opcional)</Label>
                  <Input
                    id="influx-username"
                    value={influxConfig.username}
                    onChange={(e) => setInfluxConfig({ ...influxConfig, username: e.target.value })}
                    placeholder="Deixe vazio se sem autenticação"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="influx-password">Senha (opcional)</Label>
                  <div className="relative">
                    <Input
                      id="influx-password"
                      type={showInfluxToken ? "text" : "password"}
                      value={influxConfig.password}
                      onChange={(e) => setInfluxConfig({ ...influxConfig, password: e.target.value })}
                      placeholder=""
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                      onClick={() => setShowInfluxToken(!showInfluxToken)}
                    >
                      {showInfluxToken ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">
                  Informações sobre o InfluxDB 1.8
                </h4>
                <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
                  <li>• O InfluxDB é usado para armazenar dados de medições em tempo real</li>
                  <li>• Para esta aplicação, usamos InfluxDB 1.8 (não requer token/org)</li>
                  <li>• O database <strong>db_energy</strong> será criado automaticamente</li>
                  <li>• Os dados são organizados por equipamento e timestamp</li>
                </ul>
              </div>

              <div className="flex items-center space-x-4 pt-4 border-t">
                <Button onClick={saveInfluxConfig} className="flex items-center space-x-2">
                  <Save className="h-4 w-4" />
                  <span>Salvar Configuração</span>
                </Button>

                <Button
                  variant="outline"
                  onClick={testInfluxConnection}
                  disabled={testing.influx}
                  className="flex items-center space-x-2"
                >
                  <TestTube className="h-4 w-4" />
                  <span>{testing.influx ? 'Testando...' : 'Testar Conexão'}</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

