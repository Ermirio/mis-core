import { useState, useEffect } from 'react'
import {
    Factory,
    Target,
    Brain,
    Moon,
    Sun,
    Monitor,
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

const Header = ({
    selectedLine,
    setSelectedLine,
    selectedTarget,
    setSelectedTarget,
    selectedModel,
    setSelectedModel,
    refreshTrigger
}) => {
    const { setTheme } = useTheme()
    const [lines, setLines] = useState([])
    const [targets, setTargets] = useState([])
    const [models, setModels] = useState([])

    useEffect(() => {
        loadLines()
    }, [refreshTrigger])

    useEffect(() => {
        if (selectedLine) {
            loadTargets()
        } else {
            setTargets([])
            setSelectedTarget(null)
        }
    }, [selectedLine, refreshTrigger])

    useEffect(() => {
        if (selectedTarget) {
            loadModels()
        } else {
            setModels([])
            setSelectedModel(null)
        }
    }, [selectedTarget, refreshTrigger])

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

    return (
        <header className="border-b bg-card w-full sticky top-0 z-40 shadow-sm">
            <div className="container px-4 h-16 flex items-center justify-between">
                {/* Left Side: Context Info (Optional, but useful to know what we are filtering) */}
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                    <Factory className="h-4 w-4" />
                    <span className="font-medium hidden md:inline">Contexto de Produção</span>
                </div>

                {/* Right Side: Selectors */}
                <div className="flex items-center space-x-2 md:space-x-4">
                    {/* Seletor de Linha */}
                    <Select value={selectedLine} onValueChange={setSelectedLine}>
                        <SelectTrigger className="w-[120px] md:w-[150px]">
                            <Factory className="mr-2 h-4 w-4 text-muted-foreground" />
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
                            <SelectTrigger className="w-[120px] md:w-[150px]">
                                <Target className="mr-2 h-4 w-4 text-muted-foreground" />
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
                            <SelectTrigger className="w-[120px] md:w-[150px]">
                                <Brain className="mr-2 h-4 w-4 text-muted-foreground" />
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

                    <div className="h-6 w-px bg-border mx-2"></div>

                    {/* Seletor de Tema */}
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
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
        </header>
    )
}

export default Header
