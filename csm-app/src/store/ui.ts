import { create } from 'zustand'

interface UiState {
  selectedAccountId: string | null
  selectAccount: (id: string | null) => void
}

export const useUiStore = create<UiState>()((set) => ({
  selectedAccountId: null,
  selectAccount: (id) => set({ selectedAccountId: id }),
}))
