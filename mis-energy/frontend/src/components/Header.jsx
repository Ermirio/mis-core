import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import { Menu, Bell, Settings, User, Zap, Play, Square, RotateCcw, AlertTriangle, AlertCircle, Info, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'

export function Header({ sidebarOpen, setSidebarOpen }) {
  const { toast } = useToast()
  const navigate = useNavigate()
  const dropdownRef = useRef(null)

  // Notification state
  const [notifications, setNotifications] = useState([])
  const [notificationCount, setNotificationCount] = useState(0)
  const [showNotifications, setShowNotifications] = useState(false)

  // Initialize from localStorage
  const [loading, setLoading] = useState(false);
  const [simulationActive, setSimulationActive] = useState(() => {
    return localStorage.getItem('mockMode') === 'true';
  });

  // Fetch notifications
  const fetchNotifications = async () => {
    try {
      const data = await api.get('/notifications')
      if (data.success) {
        setNotifications(data.data.notifications || [])
        setNotificationCount(data.data.count || 0)
      }
    } catch (error) {
      console.error('Error fetching notifications:', error)
    }
  }

  useEffect(() => {
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

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

    setTimeout(() => window.location.reload(), 500);
  }

  const regenerateData = async () => {
    try {
      setLoading(true)
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

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'warning': return <AlertTriangle className="h-4 w-4 text-amber-500" />
      default: return <Info className="h-4 w-4 text-blue-500" />
    }
  }

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'border-l-red-500 bg-red-50 dark:bg-red-900/20'
      case 'warning': return 'border-l-amber-500 bg-amber-50 dark:bg-amber-900/20'
      default: return 'border-l-blue-500 bg-blue-50 dark:bg-blue-900/20'
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

          {/* Notifications with Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <Button
              variant="ghost"
              size="sm"
              className="relative"
              onClick={() => setShowNotifications(!showNotifications)}
            >
              <Bell className="h-5 w-5" />
              {notificationCount > 0 && (
                <Badge
                  variant="destructive"
                  className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs"
                >
                  {notificationCount > 9 ? '9+' : notificationCount}
                </Badge>
              )}
            </Button>

            {/* Dropdown */}
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden z-50">
                <div className="p-3 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                  <h3 className="font-semibold text-slate-900 dark:text-white">Notificações</h3>
                  <Badge variant="secondary">{notificationCount} alertas</Badge>
                </div>

                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-slate-500">
                      Nenhuma notificação
                    </div>
                  ) : (
                    notifications.slice(0, 5).map((notification, idx) => (
                      <div
                        key={idx}
                        className={`p-3 border-l-4 ${getSeverityColor(notification.severity)} border-b border-slate-100 dark:border-slate-700 last:border-b-0`}
                      >
                        <div className="flex items-start gap-2">
                          {getSeverityIcon(notification.severity)}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                              {notification.title}
                            </p>
                            <p className="text-xs text-slate-500 truncate">
                              {notification.message}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="p-2 border-t border-slate-200 dark:border-slate-700">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full justify-between"
                    onClick={() => {
                      setShowNotifications(false)
                      navigate('/notifications')
                    }}
                  >
                    Ver todas as notificações
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>

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

