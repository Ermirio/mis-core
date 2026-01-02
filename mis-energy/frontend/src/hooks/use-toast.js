import { useState, useCallback, useEffect } from 'react'

// Global toast state
let toasts = []
let listeners = []
let toastId = 0

const addToast = (toast) => {
  const id = toastId++
  const newToast = { ...toast, id, timestamp: Date.now() }
  toasts = [...toasts, newToast]
  listeners.forEach(listener => listener(toasts))

  // Auto remove after 5 seconds
  setTimeout(() => {
    removeToast(id)
  }, 5000)

  return id
}

const removeToast = (id) => {
  toasts = toasts.filter(t => t.id !== id)
  listeners.forEach(listener => listener(toasts))
}

export function useToast() {
  const [, setToastState] = useState(toasts)

  useEffect(() => {
    const listener = (newToasts) => setToastState([...newToasts])
    listeners.push(listener)
    return () => {
      listeners = listeners.filter(l => l !== listener)
    }
  }, [])

  const toast = useCallback(({ title, description, variant = 'default' }) => {
    addToast({ title, description, variant })
  }, [])

  return { toast, toasts }
}

// Export for Toaster component
export function useToastState() {
  const [toastState, setToastState] = useState(toasts)

  useEffect(() => {
    const listener = (newToasts) => setToastState([...newToasts])
    listeners.push(listener)
    return () => {
      listeners = listeners.filter(l => l !== listener)
    }
  }, [])

  return { toasts: toastState, removeToast }
}
