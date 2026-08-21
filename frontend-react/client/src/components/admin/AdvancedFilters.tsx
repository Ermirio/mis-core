import React, { useState } from "react";
import { Search, Filter, X, ChevronDown } from "lucide-react";
import { Button } from "../ui/button";

interface FilterOption {
  key: string;
  label: string;
  type: 'text' | 'select' | 'date' | 'number';
  options?: { value: string; label: string }[];
}

interface AdvancedFiltersProps {
  filters: FilterOption[];
  onApplyFilters: (filters: Record<string, any>) => void;
  onClearFilters: () => void;
}

const AdvancedFilters: React.FC<AdvancedFiltersProps> = ({
  filters,
  onApplyFilters,
  onClearFilters
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [filterValues, setFilterValues] = useState<Record<string, any>>({});
  const [searchTerm, setSearchTerm] = useState("");

  const handleFilterChange = (key: string, value: any) => {
    setFilterValues(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleApply = () => {
    const activeFilters = {
      ...filterValues,
      search: searchTerm
    };
    onApplyFilters(activeFilters);
  };

  const handleClear = () => {
    setFilterValues({});
    setSearchTerm("");
    onClearFilters();
  };

  const activeFilterCount = Object.values(filterValues).filter(v => v !== '' && v !== null && v !== undefined).length + (searchTerm ? 1 : 0);

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded-lg overflow-hidden">
      {/* Search Bar */}
      <div className="p-4 flex items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-neutral-500" />
          <input
            type="text"
            placeholder="Buscar..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-neutral-900 border border-neutral-800 rounded-md text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>
        
        <Button
          onClick={() => setIsExpanded(!isExpanded)}
          variant="outline"
          className="bg-transparent border-neutral-700 text-neutral-300 hover:bg-neutral-800"
        >
          <Filter className="mr-2 h-4 w-4" />
          Filtros
          {activeFilterCount > 0 && (
            <span className="ml-2 px-2 py-0.5 bg-emerald-500 text-white text-xs rounded-full">
              {activeFilterCount}
            </span>
          )}
          <ChevronDown className={`ml-2 h-4 w-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </Button>

        <Button
          onClick={handleApply}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          Aplicar
        </Button>

        {activeFilterCount > 0 && (
          <Button
            onClick={handleClear}
            variant="ghost"
            className="text-neutral-400 hover:text-white hover:bg-neutral-800"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Advanced Filters */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-neutral-800 bg-neutral-900/50">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filters.map((filter) => (
              <div key={filter.key} className="space-y-2">
                <label className="text-xs text-neutral-500 uppercase tracking-wider">
                  {filter.label}
                </label>
                
                {filter.type === 'text' && (
                  <input
                    type="text"
                    value={filterValues[filter.key] || ''}
                    onChange={(e) => handleFilterChange(filter.key, e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-900 border border-neutral-800 rounded-md text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-emerald-500 transition-colors text-sm"
                  />
                )}

                {filter.type === 'select' && (
                  <select
                    value={filterValues[filter.key] || ''}
                    onChange={(e) => handleFilterChange(filter.key, e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-900 border border-neutral-800 rounded-md text-neutral-200 focus:outline-none focus:border-emerald-500 transition-colors text-sm"
                  >
                    <option value="">Todos</option>
                    {filter.options?.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                )}

                {filter.type === 'date' && (
                  <input
                    type="date"
                    value={filterValues[filter.key] || ''}
                    onChange={(e) => handleFilterChange(filter.key, e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-900 border border-neutral-800 rounded-md text-neutral-200 focus:outline-none focus:border-emerald-500 transition-colors text-sm"
                  />
                )}

                {filter.type === 'number' && (
                  <input
                    type="number"
                    value={filterValues[filter.key] || ''}
                    onChange={(e) => handleFilterChange(filter.key, e.target.value)}
                    className="w-full px-3 py-2 bg-neutral-900 border border-neutral-800 rounded-md text-neutral-200 focus:outline-none focus:border-emerald-500 transition-colors text-sm"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdvancedFilters;
