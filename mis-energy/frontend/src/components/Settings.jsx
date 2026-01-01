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
  EyeOff
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
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
    url: 'http://localhost:8086',
    token: '',
    org: '',
    bucket: 'energy_measurements'
  })

  const [showMysqlPassword, setShowMysqlPassword] = useState(false)
  const [showInfluxToken, setShowInfluxToken] = useState(false)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState({ mysql: false, influx: false })
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
    } catch (error) {
      console.error('Erro ao carregar configurações:', error)
    } finally {
      setLoading(false)
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

      <Tabs defaultValue="mysql" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="mysql" className="flex items-center space-x-2">
            <Database className="h-4 w-4" />
            <span>MySQL</span>
          </TabsTrigger>
          <TabsTrigger value="influxdb" className="flex items-center space-x-2">
            <Server className="h-4 w-4" />
            <span>InfluxDB</span>
          </TabsTrigger>
        </TabsList>

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
                    <span>Configuração InfluxDB</span>
                  </CardTitle>
                  <CardDescription>
                    Configure a conexão com o InfluxDB 2.0 para armazenar dados de medições em tempo real
                  </CardDescription>
                </div>
                <Badge variant="outline" className="flex items-center space-x-1">
                  <AlertCircle className="h-3 w-3 text-yellow-500" />
                  <span>Pendente</span>
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="influx-url">URL do Servidor</Label>
                <Input
                  id="influx-url"
                  value={influxConfig.url}
                  onChange={(e) => setInfluxConfig({ ...influxConfig, url: e.target.value })}
                  placeholder="http://localhost:8086"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="influx-token">Token de Acesso</Label>
                <div className="relative">
                  <Input
                    id="influx-token"
                    type={showInfluxToken ? "text" : "password"}
                    value={influxConfig.token}
                    onChange={(e) => setInfluxConfig({ ...influxConfig, token: e.target.value })}
                    placeholder="••••••••••••••••••••••••••••••••••••••••"
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

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="influx-org">Organização</Label>
                  <Input
                    id="influx-org"
                    value={influxConfig.org}
                    onChange={(e) => setInfluxConfig({ ...influxConfig, org: e.target.value })}
                    placeholder="my-org"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="influx-bucket">Bucket</Label>
                  <Input
                    id="influx-bucket"
                    value={influxConfig.bucket}
                    onChange={(e) => setInfluxConfig({ ...influxConfig, bucket: e.target.value })}
                    placeholder="energy_measurements"
                  />
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">
                  Informações sobre o InfluxDB
                </h4>
                <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
                  <li>• O InfluxDB é usado para armazenar dados de medições em tempo real</li>
                  <li>• Configure um token com permissões de leitura e escrita no bucket</li>
                  <li>• Os dados são organizados por equipamento e timestamp</li>
                  <li>• Suporte para retenção automática de dados históricos</li>
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

