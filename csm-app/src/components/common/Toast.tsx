import { useEffect } from 'react'
import { motion } from 'motion/react'
import { CheckCircle, Info, Copy } from 'lucide-react'
import type { Toast as ToastType } from '@/store/ui'

interface ToastProps {
  toast: ToastType
  onDismiss: (id: string) => void
}

const ICONS = { success: CheckCircle, info: Info, copied: Copy } as const

export default function Toast({ toast, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 3200)
    return () => clearTimeout(timer)
  }, [toast.id, onDismiss])

  const Icon = ICONS[toast.variant]

  return (
    <motion.div
      className={`toast ${toast.variant}`}
      initial={{ opacity: 0, y: 16, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      onClick={() => onDismiss(toast.id)}
    >
      <Icon size={14} />
      {toast.message}
    </motion.div>
  )
}
