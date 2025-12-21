import { ChevronRight, Home } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

interface BreadcrumbItem {
  label: string;
  path: string;
}

export default function Breadcrumbs() {
  const location = useLocation();
  
  const getBreadcrumbs = (): BreadcrumbItem[] => {
    const paths = location.pathname.split('/').filter(Boolean);
    const breadcrumbs: BreadcrumbItem[] = [
      { label: 'Home', path: '/' }
    ];
    
    let currentPath = '';
    paths.forEach((path, index) => {
      currentPath += `/${path}`;
      
      // Mapear rotas para labels amigáveis
      let label = path;
      if (path === 'factory-panel') label = 'Painel da Fábrica';
      else if (path === 'diagnosticos') label = 'Diagnósticos';
      else if (path === 'analytics') label = 'Análises';
      else if (path === 'linha') label = 'Linha';
      else if (path === 'equipamento') label = 'Equipamento';
      else if (path === 'detalhes') label = 'Detalhes';
      else if (path.startsWith('L')) label = `Linha ${path}`;
      else if (path.match(/^\d+$/)) label = `#${path}`;
      
      breadcrumbs.push({ label, path: currentPath });
    });
    
    return breadcrumbs;
  };
  
  const breadcrumbs = getBreadcrumbs();
  
  return (
    <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-4">
      {breadcrumbs.map((crumb, index) => (
        <div key={crumb.path} className="flex items-center">
          {index > 0 && <ChevronRight className="h-4 w-4 mx-2" />}
          {index === breadcrumbs.length - 1 ? (
            <span className="font-medium text-foreground">{crumb.label}</span>
          ) : (
            <Link 
              to={crumb.path}
              className="hover:text-foreground transition-colors"
            >
              {index === 0 && <Home className="h-4 w-4" />}
              {index > 0 && crumb.label}
            </Link>
          )}
        </div>
      ))}
    </nav>
  );
}
