import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Router,
  Cpu,
  Settings,
  ChevronLeft,
  Activity,
  Database,
  Wifi,
  BarChart3,
  Factory
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const navigation = [
  {
    name: 'Dashboard',
    href: '/',
    icon: LayoutDashboard,
    description: 'Visão geral do sistema'
  },
  {
    name: 'Factory View',
    href: '/factory-view',
    icon: Factory,
    description: 'Consolidado da Fábrica'
  },
  {
    name: 'Analytics',
    href: '/analytics',
    icon: BarChart3,
    description: 'Análise de consumo energético'
  },
  {
    name: 'Gateways',
    href: '/gateways',
    icon: Router,
    description: 'Gerenciar gateways Modbus'
  },
  {
    name: 'Equipamentos',
    href: '/equipments',
    icon: Cpu,
    description: 'Gerenciar equipamentos'
  },
  {
    name: 'Configurações',
    href: '/settings',
    icon: Settings,
    description: 'Configurações do sistema'
  }
]

export function Sidebar({ open, setOpen }) {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        "fixed inset-y-0 left-0 z-50 flex flex-col bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm border-r border-slate-200 dark:border-slate-700 transition-all duration-300",
        collapsed ? "w-16" : "w-64",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      )}>
        {/* Sidebar Header */}
        <div className="flex flex-col p-6 border-b border-slate-200 dark:border-slate-700">
          {!collapsed && (
            <div className="flex flex-col items-center justify-center w-full">
              <img
                src="/mis-energy/mis-energy-animation.gif"
                alt="MIS Energy Logo"
                className="w-40 h-40 object-contain"
              />
            </div>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:flex absolute top-2 right-2"
          >
            <ChevronLeft className={cn(
              "h-4 w-4 transition-transform",
              collapsed && "rotate-180"
            )} />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            const Icon = item.icon

            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center space-x-3 px-3 py-2.5 rounded-xl transition-all duration-200 group",
                  isActive
                    ? "bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg"
                    : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
                )}
              >
                <Icon className={cn(
                  "h-5 w-5 flex-shrink-0",
                  isActive ? "text-white" : "text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300"
                )} />

                {!collapsed && (
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">
                      {item.name}
                    </p>
                    <p className={cn(
                      "text-xs truncate",
                      isActive
                        ? "text-blue-100"
                        : "text-slate-500 dark:text-slate-400"
                    )}>
                      {item.description}
                    </p>
                  </div>
                )}
              </Link>
            )
          })}
        </nav>

        {/* Status Indicators */}
        {!collapsed && (
          <div className="p-4 border-t border-slate-200 dark:border-slate-700">
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600 dark:text-slate-400">Status do Sistema</span>
              </div>

              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-xs text-slate-600 dark:text-slate-400">Backend Online</span>
                </div>

                <div className="flex items-center space-x-2">
                  <Database className="h-3 w-3 text-blue-500" />
                  <span className="text-xs text-slate-600 dark:text-slate-400">MySQL Conectado</span>
                </div>

                <div className="flex items-center space-x-2">
                  <Wifi className="h-3 w-3 text-purple-500" />
                  <span className="text-xs text-slate-600 dark:text-slate-400">InfluxDB Ativo</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

