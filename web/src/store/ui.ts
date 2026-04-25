import { create } from 'zustand'

export type AppMode = 'browse' | 'search' | 'review'

interface UiState {
  mode: AppMode
  selectedEntityId: string | null
  expandedPaths: Set<string>
  setMode: (mode: AppMode) => void
  selectEntity: (id: string | null) => void
  togglePath: (path: string) => void
  expandPath: (path: string) => void
}

export const useUiStore = create<UiState>()((set) => ({
  mode: 'browse',
  selectedEntityId: null,
  expandedPaths: new Set<string>(['/static', '/procedural', '/trajectory']),

  setMode: (mode) => set({ mode }),

  selectEntity: (id) => set({ selectedEntityId: id }),

  togglePath: (path) =>
    set((s) => {
      const next = new Set(s.expandedPaths)
      next.has(path) ? next.delete(path) : next.add(path)
      return { expandedPaths: next }
    }),

  expandPath: (path) =>
    set((s) => ({ expandedPaths: new Set(s.expandedPaths).add(path) })),
}))
