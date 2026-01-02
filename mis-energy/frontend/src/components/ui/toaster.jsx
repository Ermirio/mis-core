import { useToastState } from '@/hooks/use-toast'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'

export function Toaster() {
    const { toasts, removeToast } = useToastState()

    if (toasts.length === 0) return null

    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
            {toasts.map((toast) => (
                <div
                    key={toast.id}
                    className={`
            flex items-start gap-3 p-4 rounded-lg shadow-lg border backdrop-blur-sm
            animate-in slide-in-from-right-5 duration-200
            ${toast.variant === 'destructive'
                            ? 'bg-red-50 border-red-200 text-red-900 dark:bg-red-900/90 dark:border-red-800 dark:text-red-100'
                            : toast.variant === 'success'
                                ? 'bg-green-50 border-green-200 text-green-900 dark:bg-green-900/90 dark:border-green-800 dark:text-green-100'
                                : 'bg-white border-slate-200 text-slate-900 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100'
                        }
          `}
                >
                    {/* Icon */}
                    <div className="flex-shrink-0 mt-0.5">
                        {toast.variant === 'destructive' ? (
                            <AlertCircle className="h-5 w-5 text-red-500" />
                        ) : toast.variant === 'success' ? (
                            <CheckCircle className="h-5 w-5 text-green-500" />
                        ) : (
                            <Info className="h-5 w-5 text-blue-500" />
                        )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        {toast.title && (
                            <p className="font-medium text-sm">{toast.title}</p>
                        )}
                        {toast.description && (
                            <p className="text-sm opacity-90 mt-0.5">{toast.description}</p>
                        )}
                    </div>

                    {/* Close button */}
                    <button
                        onClick={() => removeToast(toast.id)}
                        className="flex-shrink-0 p-1 rounded-md hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
            ))}
        </div>
    )
}
