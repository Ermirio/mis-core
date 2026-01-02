import { useState, useEffect } from 'react'
import api from '../services/api'
import { Menu, Bell, Settings, User, Zap, Play, Square, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'

export function Header({ sidebarOpen, setSidebarOpen }) {
  const { toast } = useToast()

  // Initialize from localStorage
  const [simulationActive, setSimulationActive] = useState(() => {
    return localStorage.getItem('mockMode') === 'true';
  });

  const toggleSimulation = () => {
    const newState = !simulationActive;
    setSimulationActive(newState);
    localStorage.setItem('mockMode', newState);

    toast({
      title: newState ? "Modo Mock Ativado" : "Modo Real Ativado",
      description: newState
        ? "Visualizando dados simulados/fakes. Use apenas para validação."
        : "Visualizando dados reais do chão de fábrica.",
      variant: newState ? "secondary" : "default"
    });

    // Optional: Reload to refresh all components with new mode immediately
    // or rely on next fetch. A reload is safer to ensure all stale data is cleared.
    setTimeout(() => window.location.reload(), 500);
  }

  const regenerateData = async () => {
    try {
      setLoading(true)
      // Keep this for regenerating backend fake data if needed
      const data = await api.post('/simulation/regenerate')

      if (data.success) {
        toast({
          title: "Dados Regenerados",
          description: "Novos dados aleatórios gerados.",
          variant: "default"
        })
        window.location.reload()
      }
    } catch (error) {
      toast({
        title: "Erro",
        description: "Erro ao regenerar dados",
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

