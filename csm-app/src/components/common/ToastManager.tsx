import { AnimatePresence } from 'motion/react'
import { useUiStore } from '@/store/ui'
import Toast from './Toast'

export default function ToastManager() {
  const toasts = useUiStore((s) => s.toasts)
  const removeToast = useUiStore((s) => s.removeToast)

  return (
    <div className="toast-container">
      <AnimatePresence>
        {toasts.map((t) => (
          <Toast key={t.id} toast={t} onDismiss={removeToast} />
        ))}
      </AnimatePresence>
    </div>
  )
}
