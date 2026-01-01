import { useState, useCallback } from 'react'

const toasts = []
let toastId = 0

export function useToast() {
  const [, forceUpdate] = useState({})

  const toast = useCallback(({ title, description, variant = 'default' }) => {
    const id = toastId++
    const newToast = {
      id,
      title,
      description,
      variant,
      timestamp: Date.now()
    }

    toasts.push(newToast)
    forceUpdate({})

    // Auto remove after 5 seconds
    setTimeout(() => {
      const index = toasts.findIndex(t => t.id === id)
      if (index > -1) {
        toasts.splice(index, 1)
        forceUpdate({})
      }
    }, 5000)

    // Show browser notification for important messages
    if (variant === 'destructive') {
      console.error(`${title}: ${description}`)
    } else {
      console.log(`${title}: ${description}`)
    }
  }, [])

  return { toast }
}

