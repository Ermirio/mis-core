import { useState, useEffect } from "react";
import { AlertCircle, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const DJANGO_API_URL = import.meta.env.VITE_DJANGO_API_URL || "http://127.0.0.1:8000/api";
const FLASK_API_URL = import.meta.env.VITE_FLASK_API_URL || "http://127.0.0.1:5000/api";

interface ServiceStatus {
  name: string;
  status: 'online' | 'offline' | 'checking';
  responseTime?: number;
}

export default function SystemStatus() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'Django API', status: 'checking' },
    { name: 'Flask API', status: 'checking' },
  ]);
  
  const checkServiceHealth = async (url: string, name: string) => {
    const startTime = Date.now();
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(url, {
        signal: controller.signal,
        method: 'GET',
      });
      
      clearTimeout(timeoutId);
      const responseTime = Date.now() - startTime;
      
      return {
        name,
        status: response.ok ? 'online' as const : 'offline' as const,
        responseTime
      };
    } catch (error) {
      return {
        name,
        status: 'offline' as const,
        responseTime: undefined
      };
    }
  };
  
  const checkAllServices = async () => {
    const [djangoStatus, flaskStatus] = await Promise.all([
      checkServiceHealth(`${DJANGO_API_URL}/linhas/`, 'Django API'),
      checkServiceHealth(`${FLASK_API_URL}/health`, 'Flask API'),
    ]);
    
    setServices([djangoStatus, flaskStatus]);
  };
  
  useEffect(() => {
    checkAllServices();
    
    // Verificar a cada 30 segundos
    const interval = setInterval(checkAllServices, 30000);
    
    return () => clearInterval(interval);
  }, []);
  
  const getStatusIcon = (status: ServiceStatus['status']) => {
    switch (status) {
      case 'online':
        return <CheckCircle className="h-3 w-3 text-green-500" />;
      case 'offline':
        return <XCircle className="h-3 w-3 text-red-500" />;
      case 'checking':
        return <Loader2 className="h-3 w-3 animate-spin text-yellow-500" />;
    }
  };
  
  const getStatusVariant = (status: ServiceStatus['status']) => {
    switch (status) {
      case 'online':
        return 'default';
      case 'offline':
        return 'destructive';
      case 'checking':
        return 'secondary';
    }
  };
  
  const allOnline = services.every(s => s.status === 'online');
  const anyOffline = services.some(s => s.status === 'offline');
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-2">
            {allOnline && <CheckCircle className="h-4 w-4 text-green-500" />}
            {anyOffline && <AlertCircle className="h-4 w-4 text-red-500" />}
            {!allOnline && !anyOffline && <Loader2 className="h-4 w-4 animate-spin text-yellow-500" />}
            <span className="text-sm font-medium">
              {allOnline ? 'Sistema OK' : anyOffline ? 'Falha no Sistema' : 'Verificando...'}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="w-64">
          <div className="space-y-2">
            <p className="font-semibold text-sm mb-2">Status dos Serviços</p>
            {services.map((service) => (
              <div key={service.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getStatusIcon(service.status)}
                  <span className="text-sm">{service.name}</span>
                </div>
                <Badge variant={getStatusVariant(service.status)} className="text-xs">
                  {service.status === 'online' && service.responseTime 
                    ? `${service.responseTime}ms` 
                    : service.status}
                </Badge>
              </div>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
