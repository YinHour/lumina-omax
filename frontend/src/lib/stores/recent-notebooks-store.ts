import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface RecentNotebookItem {
  id: string
  name: string
  openedAt: number
}

interface RecentNotebooksState {
  recentNotebooks: RecentNotebookItem[]
  recordNotebook: (item: { id: string; name: string }) => void
}

const MAX_RECENT_NOTEBOOKS = 5

export const useRecentNotebooksStore = create<RecentNotebooksState>()(
  persist(
    (set) => ({
      recentNotebooks: [],
      recordNotebook: (item) => set((state) => {
        const nextItem = {
          ...item,
          openedAt: Date.now(),
        }
        const deduped = state.recentNotebooks.filter(
          (notebook) => notebook.id !== item.id
        )
        return {
          recentNotebooks: [nextItem, ...deduped].slice(0, MAX_RECENT_NOTEBOOKS),
        }
      }),
    }),
    {
      name: 'recent-notebooks-storage',
    }
  )
)
