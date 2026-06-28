import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AskCoverage } from '@/lib/types/search'

export interface StrategyData {
  reasoning: string
  searches: Array<{ term: string; instructions: string }>
}

export interface AskHistoryEntry {
  id: string
  question: string
  answer: string
  coverage: AskCoverage | null
  createdAt: string
}

interface AskState {
  isStreaming: boolean
  strategy: StrategyData | null
  answers: string[]
  finalAnswer: string | null
  coverage: AskCoverage | null
  history: AskHistoryEntry[]
  error: string | null
  errorBubble: string | null
  activityElapsedSeconds: number
  abortController: AbortController | null

  setStreaming: (isStreaming: boolean) => void
  setStrategy: (strategy: StrategyData | null) => void
  updateStrategyReasoning: (chunk: string) => void
  addAnswer: (answer: string) => void
  setFinalAnswer: (answer: string) => void
  setCoverage: (coverage: AskCoverage | null) => void
  addHistoryEntry: (entry: Omit<AskHistoryEntry, 'id' | 'createdAt'>) => void
  restoreHistoryEntry: (id: string) => AskHistoryEntry | null
  clearHistory: () => void
  setError: (error: string | null) => void
  setErrorBubble: (body: string | null) => void
  setActivityElapsedSeconds: (seconds: number) => void
  setAbortController: (controller: AbortController | null) => void
  clearState: () => void
}

export const useAskStore = create<AskState>()(
  persist(
    (set, get) => ({
      isStreaming: false,
      strategy: null,
      answers: [],
      finalAnswer: null,
      coverage: null,
      history: [],
      error: null,
      errorBubble: null,
      activityElapsedSeconds: 0,
      abortController: null,

      setStreaming: (isStreaming) => set({ isStreaming }),
      setStrategy: (strategy) => set({ strategy }),
      updateStrategyReasoning: (chunk) => set((state) => ({
        strategy: {
          reasoning: (state.strategy?.reasoning || '') + chunk,
          searches: state.strategy?.searches || []
        }
      })),
      addAnswer: (answer) => set((state) => ({
        answers: [...state.answers, answer]
      })),
      setFinalAnswer: (finalAnswer) => set({ finalAnswer, isStreaming: false }),
      setCoverage: (coverage) => set({ coverage }),
      addHistoryEntry: (entry) => set((state) => ({
        history: [
          {
            ...entry,
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            createdAt: new Date().toISOString(),
          },
          ...state.history,
        ].slice(0, 50),
      })),
      restoreHistoryEntry: (id) => {
        const entry = get().history.find((item) => item.id === id) || null
        if (entry) {
          set({
            strategy: null,
            answers: [],
            finalAnswer: entry.answer,
            coverage: entry.coverage,
            error: null,
            errorBubble: null,
            activityElapsedSeconds: 0,
            isStreaming: false,
          })
        }
        return entry
      },
      clearHistory: () => set({ history: [] }),
      setError: (error) => set({ error, isStreaming: false }),
      setErrorBubble: (errorBubble) => set({ errorBubble, isStreaming: false }),
      setActivityElapsedSeconds: (activityElapsedSeconds) => set({ activityElapsedSeconds }),
      setAbortController: (controller) => set({ abortController: controller }),
      clearState: () => {
        const { abortController } = get()
        if (abortController) {
          abortController.abort()
        }
        set({
          isStreaming: false,
          strategy: null,
          answers: [],
          finalAnswer: null,
          coverage: null,
          error: null,
          errorBubble: null,
          activityElapsedSeconds: 0,
          abortController: null
        })
      }
    }),
    {
      name: 'ask-store-state',
      partialize: (state) => ({
        strategy: state.strategy,
        answers: state.answers,
        finalAnswer: state.finalAnswer,
        coverage: state.coverage,
        history: state.history,
        error: state.error
        // Exclude isStreaming, errorBubble, activityElapsedSeconds, abortController
      })
    }
  )
)
