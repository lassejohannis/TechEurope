import { create } from 'zustand'

export interface Toast {
  id: string
  message: string
  variant: 'success' | 'info' | 'copied'
}

interface UiState {
  selectedAccountId: string | null
  handledItems: Set<string>
  taskNotes: Record<string, string>
  toasts: Toast[]
  selectAccount: (id: string | null) => void
  markHandled: (id: string) => void
  setTaskNote: (taskId: string, note: string) => void
  addToast: (message: string, variant?: Toast['variant']) => void
  removeToast: (id: string) => void
}

export const useUiStore = create<UiState>()((set) => ({
  selectedAccountId: null,
  handledItems: new Set<string>(),
  taskNotes: {},
  toasts: [],
  selectAccount: (id) => set({ selectedAccountId: id }),
  markHandled: (id) =>
    set((s) => {
      const next = new Set(s.handledItems)
      next.add(id)
      return { handledItems: next }
    }),
  setTaskNote: (taskId, note) =>
    set((s) => ({ taskNotes: { ...s.taskNotes, [taskId]: note } })),
  addToast: (message, variant = 'success') =>
    set((s) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`
      return { toasts: [...s.toasts, { id, message, variant }] }
    }),
  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
