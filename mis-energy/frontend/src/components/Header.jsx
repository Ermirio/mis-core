import { useState, useEffect } from 'react'
import api from '../services/api'
import { Menu, Bell, Settings, User, Zap, Play, Square, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'

export function Header({ sidebarOpen, setSidebarOpen }) {
  const [simulationActive, setSimulationActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    checkSimulationStatus()
  }, [])

  const checkSimulationStatus = async () => {
    try {
      const data = await api.get('/simulation/status')

      if (data.success) {
        setSimulationActive(data.data.simulation_active)
      }
    } catch (error) {
      console.error('Erro ao verificar status da simulação:', error)
    }
  }

  const toggleSimulation = async () => {
    try {
      setLoading(true)
      const data = await api.post('/simulation/toggle')

      if (data.success) {
        setSimulationActive(data.data.simulation_active)
        toast({
          title: "Modo Simulação",
          description: data.data.message,
          variant: data.data.simulation_active ? "default" : "destructive"
        })
      } else {
        toast({
          title: "Erro",
          description: data.error || "Erro ao alternar modo simulação",
          variant: "destructive"
        })
      }
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro de conexão ao alternar simulação",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const regenerateData = async () => {
    try {
      setLoading(true)
      const data = await api.post('/simulation/regenerate')

      if (data.success) {
        toast({
          title: "Dados Regenerados",
          description: "Dados simulados foram regenerados com sucesso",
          variant: "default"
        })
        // Recarregar a página para atualizar os dados
        window.location.reload()
      } else {
        toast({
          title: "Erro",
          description: data.error || "Erro ao regenerar dados",
          variant: "destructive"
        })
      }
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro de conexão ao regenerar dados",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <header className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700 sticky top-0 z-40">
      <div className="flex items-center justify-between px-6 py-4">
        {/* Left Section */}
        <div className="flex items-center space-x-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl">
              <Zap className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                Sistema de Monitoramento Energético
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                MIS Developed By Process Engineer
              </p>
            </div>
          </div>
        </div>

        {/* Right Section */}
        <div className="flex items-center space-x-4">
          {/* Simulation Controls */}
          <div className="flex items-center space-x-2 border-r border-slate-200 dark:border-slate-700 pr-4">
            {simulationActive && (
              <Badge variant="secondary" className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                Simulação Ativa
              </Badge>
            )}

            <Button
              variant={simulationActive ? "destructive" : "default"}
              size="sm"
              onClick={toggleSimulation}
              disabled={loading}
              className="flex items-center space-x-2"
            >
              {simulationActive ? (
                <>
                  <Square className="h-4 w-4" />
                  <span className="hidden sm:inline">Parar</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  <span className="hidden sm:inline">Simular</span>
                </>
              )}
            </Button>

            {simulationActive && (
              <Button
                variant="outline"
                size="sm"
                onClick={regenerateData}
                disabled={loading}
                className="flex items-center space-x-2"
              >
                <RotateCcw className="h-4 w-4" />
                <span className="hidden sm:inline">Regenerar</span>
              </Button>
            )}
          </div>

          {/* Notifications */}
          <Button variant="ghost" size="sm" className="relative">
            <Bell className="h-5 w-5" />
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs"
            >
              3
            </Badge>
          </Button>

          {/* Settings */}
          <Button variant="ghost" size="sm">
            <Settings className="h-5 w-5" />
          </Button>

          {/* User Profile */}
          <Button variant="ghost" size="sm" className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-br from-green-400 to-blue-500 rounded-full flex items-center justify-center">
              <User className="h-4 w-4 text-white" />
            </div>
            <span className="hidden md:block text-sm font-medium">Admin</span>
          </Button>
        </div>
      </div>
    </header>
  )
}

