import { useState, useEffect, useMemo } from 'react'
import api from '../services/api'
import { Bell, AlertTriangle, AlertCircle, Info, Filter, RefreshCw, Calendar, Building2, Gauge } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export function Notifications() {
    const [notifications, setNotifications] = useState([])
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)

    // Filters
    const [severityFilter, setSeverityFilter] = useState('all')
    const [typeFilter, setTypeFilter] = useState('all')

    const fetchNotifications = async () => {
        try {
            setRefreshing(true)
            const data = await api.get('/notifications')
            if (data.success) {
                setNotifications(data.data.notifications || [])
            }
        } catch (error) {
            console.error('Error fetching notifications:', error)
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }

    useEffect(() => {
        fetchNotifications()
        const interval = setInterval(fetchNotifications, 30000)
        return () => clearInterval(interval)
    }, [])

    // Filter notifications
    const filteredNotifications = useMemo(() => {
        return notifications.filter(n => {
            if (severityFilter !== 'all' && n.severity !== severityFilter) return false
            if (typeFilter !== 'all' && n.type !== typeFilter) return false
            return true
        })
    }, [notifications, severityFilter, typeFilter])

    // Group by equipment
    const groupedByEquipment = useMemo(() => {
        const groups = {}
        filteredNotifications.forEach(n => {
            const key = n.equipment_name || 'Outros'
            if (!groups[key]) groups[key] = []
            groups[key].push(n)
        })
        return groups
    }, [filteredNotifications])

    const getSeverityIcon = (severity) => {
        switch (severity) {
            case 'critical': return <AlertCircle className="h-5 w-5 text-red-500" />
            case 'warning': return <AlertTriangle className="h-5 w-5 text-amber-500" />
            default: return <Info className="h-5 w-5 text-blue-500" />
        }
    }

    const getSeverityBadge = (severity) => {
        switch (severity) {
            case 'critical':
                return <Badge variant="destructive">Crítico</Badge>
            case 'warning':
                return <Badge className="bg-amber-500 hover:bg-amber-600">Atenção</Badge>
            default:
                return <Badge variant="secondary">Info</Badge>
        }
    }

    const getTypeLabel = (type) => {
        switch (type) {
            case 'production_low': return 'Produção Baixa'
            case 'consumption_high': return 'Consumo Alto'
            case 'efficiency_high': return 'Eficiência Alta'
            case 'power_factor_low': return 'FP Baixo'
            default: return type
        }
    }

    // Stats
    const criticalCount = notifications.filter(n => n.severity === 'critical').length
    const warningCount = notifications.filter(n => n.severity === 'warning').length

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <Bell className="h-6 w-6 text-blue-500" />
                        Central de Notificações
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-1">
                        Monitore alertas e desvios do sistema em tempo real
                    </p>
                </div>
                <Button onClick={fetchNotifications} disabled={refreshing} variant="outline">
                    <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                    Atualizar
                </Button>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="border-l-4 border-l-red-500">
                    <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-slate-500">Alertas Críticos</p>
                                <p className="text-2xl font-bold text-red-600">{criticalCount}</p>
                            </div>
                            <AlertCircle className="h-8 w-8 text-red-500 opacity-50" />
                        </div>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-amber-500">
                    <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-slate-500">Avisos</p>
                                <p className="text-2xl font-bold text-amber-600">{warningCount}</p>
                            </div>
                            <AlertTriangle className="h-8 w-8 text-amber-500 opacity-50" />
                        </div>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-blue-500">
                    <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-slate-500">Total de Alertas</p>
                                <p className="text-2xl font-bold text-blue-600">{notifications.length}</p>
                            </div>
                            <Bell className="h-8 w-8 text-blue-500 opacity-50" />
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Filters */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Filter className="h-5 w-5" />
                        Filtros
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-wrap gap-4">
                        <div className="w-48">
                            <label className="text-sm text-slate-500 mb-1 block">Severidade</label>
                            <Select value={severityFilter} onValueChange={setSeverityFilter}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">Todos</SelectItem>
                                    <SelectItem value="critical">Crítico</SelectItem>
                                    <SelectItem value="warning">Atenção</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="w-48">
                            <label className="text-sm text-slate-500 mb-1 block">Tipo</label>
                            <Select value={typeFilter} onValueChange={setTypeFilter}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">Todos</SelectItem>
                                    <SelectItem value="production_low">Produção Baixa</SelectItem>
                                    <SelectItem value="consumption_high">Consumo Alto</SelectItem>
                                    <SelectItem value="efficiency_high">Eficiência Alta</SelectItem>
                                    <SelectItem value="power_factor_low">FP Baixo</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Notifications List */}
            {loading ? (
                <div className="flex items-center justify-center h-64">
                    <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
                </div>
            ) : filteredNotifications.length === 0 ? (
                <Card>
                    <CardContent className="py-12 text-center">
                        <Bell className="h-12 w-12 text-slate-300 mx-auto mb-4" />
                        <p className="text-slate-500">Nenhuma notificação encontrada</p>
                        <p className="text-sm text-slate-400 mt-1">
                            Os alertas aparecerão aqui quando houver desvios no sistema
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-4">
                    {Object.entries(groupedByEquipment).map(([equipmentName, alerts]) => (
                        <Card key={equipmentName}>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Gauge className="h-4 w-4 text-slate-400" />
                                    {equipmentName}
                                    <Badge variant="outline" className="ml-2">{alerts.length} alerta(s)</Badge>
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {alerts.map((notification, idx) => (
                                    <div
                                        key={idx}
                                        className={`p-3 rounded-lg border-l-4 ${notification.severity === 'critical'
                                                ? 'border-l-red-500 bg-red-50 dark:bg-red-900/20'
                                                : 'border-l-amber-500 bg-amber-50 dark:bg-amber-900/20'
                                            }`}
                                    >
                                        <div className="flex items-start gap-3">
                                            {getSeverityIcon(notification.severity)}
                                            <div className="flex-1">
                                                <div className="flex items-center justify-between">
                                                    <p className="font-medium text-slate-900 dark:text-white">
                                                        {notification.title}
                                                    </p>
                                                    <div className="flex items-center gap-2">
                                                        <Badge variant="outline" className="text-xs">
                                                            {getTypeLabel(notification.type)}
                                                        </Badge>
                                                        {getSeverityBadge(notification.severity)}
                                                    </div>
                                                </div>
                                                <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">
                                                    {notification.message}
                                                </p>
                                                {notification.value != null && notification.target != null && (
                                                    <div className="mt-2 flex items-center gap-4 text-xs text-slate-500">
                                                        <span>Valor atual: <strong>{notification.value}</strong></span>
                                                        <span>Meta: <strong>{notification.target}</strong></span>
                                                        {notification.percent != null && (
                                                            <span>Desvio: <strong>{notification.percent.toFixed(0)}%</strong></span>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    )
}
