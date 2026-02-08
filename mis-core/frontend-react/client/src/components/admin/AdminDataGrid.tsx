import React from "react";

interface Column<T> {
    key: keyof T | "actions";
    header: string;
    render?: (item: T) => React.ReactNode;
    width?: string;
}

interface AdminDataGridProps<T> {
    columns: Column<T>[];
    data: T[];
    loading?: boolean;
    onRowClick?: (item: T) => void;
    title?: string;
    actions?: React.ReactNode;

    // Server-side pagination props
    page?: number;
    pageSize?: number;
    total?: number;
    onPageChange?: (page: number) => void;
}

// ISA 101 High Performance Data Grid
// - Dense rows
// - Monospace font for numbers
// - High contrast for values
// - Subtle borders
function AdminDataGrid<T extends { id: string | number }>({
    columns,
    data,
    loading,
    onRowClick,
    title,
    actions,
    page = 1,
    pageSize = 50,
    total = 0,
    onPageChange
}: AdminDataGridProps<T>) {

    const totalPages = Math.ceil((total || data.length) / pageSize);
    const hasPagination = !!onPageChange;

    return (
        <div className="admin-datagrid flex flex-col h-full bg-neutral-950 border border-neutral-800 rounded-lg overflow-hidden">
            {(title || actions) && (
                <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 bg-neutral-900/50">
                    {title && <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">{title}</h3>}
                    <div className="flex items-center gap-2">
                        {actions}
                    </div>
                </div>
            )}

            <div className="flex-1 overflow-auto">
                <table className="w-full text-left border-collapse">
                    <thead className="bg-neutral-900 sticky top-0 z-10">
                        <tr>
                            {columns.map((col) => (
                                <th
                                    key={String(col.key)}
                                    className="px-4 py-2 text-xs font-medium text-neutral-500 uppercase tracking-wider border-b border-neutral-800"
                                    style={{ width: col.width }}
                                >
                                    {col.header}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800">
                        {loading ? (
                            <tr>
                                <td colSpan={columns.length} className="px-4 py-8 text-center text-neutral-500">
                                    <div className="flex items-center justify-center gap-2">
                                        <div className="w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
                                        <span>Carregando dados...</span>
                                    </div>
                                </td>
                            </tr>
                        ) : data.length === 0 ? (
                            <tr>
                                <td colSpan={columns.length} className="px-4 py-8 text-center text-neutral-600 italic">
                                    Nenhum registro encontrado.
                                </td>
                            </tr>
                        ) : (
                            data.map((item, index) => (
                                <tr
                                    key={item.id}
                                    onClick={() => onRowClick?.(item)}
                                    className={`
                    group transition-colors duration-75
                    ${index % 2 === 0 ? "bg-neutral-950" : "bg-neutral-900/30"}
                    hover:bg-neutral-800 cursor-pointer
                  `}
                                >
                                    {columns.map((col) => (
                                        <td
                                            key={String(col.key)}
                                            className="px-4 py-2 text-sm text-neutral-300 border-r border-neutral-800/50 last:border-r-0 font-mono"
                                        >
                                            {col.render ? col.render(item) : String(item[col.key] as any)}
                                        </td>
                                    ))}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            <div className="px-4 py-2 border-t border-neutral-800 bg-neutral-900 text-xs text-neutral-500 flex justify-between items-center">
                <span>Total: {total > 0 ? total : data.length} registros</span>

                {hasPagination && total > 0 && (
                    <div className="flex gap-2 items-center">
                        <button
                            disabled={page === 1}
                            onClick={() => onPageChange(page - 1)}
                            className="px-2 py-1 bg-neutral-800 rounded hover:bg-neutral-700 disabled:opacity-50 text-neutral-300 hover:text-white"
                        >
                            &lt;
                        </button>
                        <span className="text-neutral-400">Pág. {page} / {totalPages || 1}</span>
                        <button
                            disabled={page >= totalPages}
                            onClick={() => onPageChange(page + 1)}
                            className="px-2 py-1 bg-neutral-800 rounded hover:bg-neutral-700 disabled:opacity-50 text-neutral-300 hover:text-white"
                        >
                            &gt;
                        </button>
                    </div>
                )}

                <span className="hidden sm:inline">ISA 101 Compliant View</span>
            </div>
        </div>
    );
}

export default AdminDataGrid;
