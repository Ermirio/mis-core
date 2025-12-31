import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Factory,
  Target,
  Brain,
  Database,
  TrendingUp,
  Settings,
  Moon,
  Sun,
  Monitor,
  ChevronDown
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useTheme } from '@/components/theme-provider'
import { api } from '@/lib/api'

const Navbar = ({
  selectedLine,
  setSelectedLine,
  selectedTarget,
  setSelectedTarget,
  selectedModel,
  setSelectedModel,
  refreshTrigger // <-- Nova prop
}) => {
  const location = useLocation()
  const { setTheme } = useTheme()
  const [lines, setLines] = useState([])
  const [targets, setTargets] = useState([])
  const [models, setModels] = useState([])

  useEffect(() => {
    loadLines()
  }, [refreshTrigger]) // <-- Recarrega quando refreshTrigger mudar

  useEffect(() => {
    if (selectedLine) {
      loadTargets()
    } else {
      setTargets([])
      setSelectedTarget(null)
    }
  }, [selectedLine, refreshTrigger]) // <-- Recarrega quando refreshTrigger mudar

  useEffect(() => {
    if (selectedTarget) {
      loadModels()
    } else {
      setModels([])
      setSelectedModel(null)
    }
  }, [selectedTarget, refreshTrigger]) // <-- Recarrega quando refreshTrigger mudar

  const loadLines = async () => {
    try {
      const data = await api.getLines()
      setLines(data)
      if (data.length > 0 && !selectedLine) {
        setSelectedLine(data[0].name)
      }
    } catch (error) {
      console.error('Erro ao carregar linhas:', error)
    }
  }

  const loadTargets = async () => {
    try {
      const data = await api.getTargets(selectedLine)
      setTargets(data)
      // Mantém o target selecionado se ele ainda existir na nova lista, senão pega o primeiro
      if (data.length > 0) {
        if (!selectedTarget || !data.find(t => t.id === selectedTarget.id)) {
          setSelectedTarget(data[0])
        }
      } else {
        setSelectedTarget(null)
      }
    } catch (error) {
      console.error('Erro ao carregar targets:', error)
    }
  }

  const loadModels = async () => {
    try {
      const data = await api.getModels(selectedTarget.id)
      setModels(data)
      // Mantém o modelo selecionado se ele ainda existir na nova lista, senão pega o primeiro
      if (data.length > 0) {
        if (!selectedModel || !data.find(m => m.id === selectedModel.id)) {
          setSelectedModel(data[0])
        }
      } else {
        setSelectedModel(null)
      }
    } catch (error) {
      console.error('Erro ao carregar modelos:', error)
    }
  }

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: TrendingUp },
    { path: '/lines', label: 'Linhas', icon: Factory },
    { path: '/targets', label: 'Targets', icon: Target },
    { path: '/models', label: 'Modelos', icon: Brain },
    { path: '/data', label: 'Dados', icon: Database },
    { path: '/prediction', label: 'Predição', icon: TrendingUp },
    { path: '/analysis', label: 'Análise Detalhada', icon: TrendingUp }, // <-- Novo Link
    { path: '/opc', label: 'OPC', icon: Settings },
  ]

  return (
    <nav className="border-b bg-card">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo e Título */}
          <div className="flex items-center space-x-4">
            <Factory className="h-8 w-8 text-primary" />
            <h1 className="text-xl font-bold">MIS AI - Manufacture Integrated System</h1>
          </div>

          {/* Navegação Principal */}
          <div className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path

              return (
                <Link key={item.path} to={item.path}>
                  <Button
                    variant={isActive ? 'default' : 'ghost'}
                    size="sm"
                    className="flex items-center space-x-2"
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </Button>
                </Link>
              )
            })}
          </div>

          {/* Seletores e Controles */}
          <div className="flex items-center space-x-4">
            {/* Seletor de Linha */}
            <Select value={selectedLine} onValueChange={setSelectedLine}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Linha" />
              </SelectTrigger>
              <SelectContent>
                {lines.map((line) => (
                  <SelectItem key={line.id} value={line.name}>
                    {line.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Seletor de Target */}
            {targets.length > 0 && (
              <Select
                value={selectedTarget?.id?.toString() || ''}
                onValueChange={(value) => {
                  const target = targets.find(t => t.id.toString() === value)
                  setSelectedTarget(target)
                }}
              >
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Target" />
                </SelectTrigger>
                <SelectContent>
                  {targets.map((target) => (
                    <SelectItem key={target.id} value={target.id.toString()}>
                      {target.target_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* Seletor de Modelo */}
            {models.length > 0 && (
              <Select
                value={selectedModel?.id?.toString() || ''}
                onValueChange={(value) => {
                  const model = models.find(m => m.id.toString() === value)
                  setSelectedModel(model)
                }}
              >
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Modelo" />
                </SelectTrigger>
                <SelectContent>
                  {models.map((model) => (
                    <SelectItem key={model.id} value={model.id.toString()}>
                      {model.model_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* Seletor de Tema */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                  <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
                  <span className="sr-only">Alternar tema</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setTheme("light")}>
                  <Sun className="mr-2 h-4 w-4" />
                  Claro
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setTheme("dark")}>
                  <Moon className="mr-2 h-4 w-4" />
                  Escuro
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setTheme("system")}>
                  <Monitor className="mr-2 h-4 w-4" />
                  Sistema
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </nav>
  )
}

export default Navbar

