'use client'

import { useCallback, useMemo } from 'react'
import { toast } from '@/lib/hooks/use-toast'
import { useTranslation } from '@/lib/hooks/use-translation'
import { getApiErrorMessage } from '@/lib/utils/error-handler'
import { searchApi } from '@/lib/api/search'
import { AskStreamEvent } from '@/lib/types/search'
import { useAskStore } from '@/lib/stores/ask-store'

interface AskModels {
  strategy: string
  answer: string
  finalAnswer: string
}

export function useAsk() {
  const { t } = useTranslation()
  const store = useAskStore()

  const sendAsk = useCallback(async (question: string, models: AskModels) => {
    // Validate inputs
    if (!question.trim()) {
      toast.error(t('apiErrors.pleaseEnterQuestion'))
      return
    }

    if (!models.strategy || !models.answer || !models.finalAnswer) {
      toast.error(t('apiErrors.pleaseConfigureModels'))
      return
    }

    // Reset state and cancel any ongoing request
    useAskStore.getState().clearState()
    
    const abortController = new AbortController()
    useAskStore.getState().setAbortController(abortController)
    useAskStore.getState().setStreaming(true)

    try {
      const response = await searchApi.askKnowledgeBase({
        question,
        strategy_model: models.strategy,
        answer_model: models.answer,
        final_answer_model: models.finalAnswer
      }, abortController.signal)

      if (!response) {
        throw new Error('No response body received from server')
      }

      const reader = response.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')

        // Keep the last incomplete line in buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6).trim()
              if (!jsonStr) continue

              const data: AskStreamEvent = JSON.parse(jsonStr)

              if (data.type === 'strategy') {
                useAskStore.getState().setStrategy({
                  reasoning: data.reasoning || useAskStore.getState().strategy?.reasoning || '',
                  searches: data.searches || []
                })
              } else if (data.type === 'strategy_reasoning_chunk') {
                useAskStore.getState().updateStrategyReasoning(data.chunk || '')
              } else if (data.type === 'answer') {
                useAskStore.getState().addAnswer(data.content || '')
              } else if (data.type === 'final_answer') {
                useAskStore.getState().setFinalAnswer(data.content || '')
              } else if (data.type === 'complete') {
                useAskStore.getState().setStreaming(false)
              } else if (data.type === 'error') {
                throw new Error(data.message || 'Stream error occurred')
              }
            } catch (e) {
              if (e instanceof SyntaxError) {
                console.error('Error parsing SSE data:', e, 'Line:', line)
                // Don't throw - continue processing other lines
              } else {
                throw e
              }
            }
          }
        }
      }

      // Ensure streaming is stopped
      useAskStore.getState().setStreaming(false)

    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Ask request aborted')
        return
      }

      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred'
      console.error('Ask error:', error)

      useAskStore.getState().setError(errorMessage)

      toast.error(t('apiErrors.askFailed'), {
        description: getApiErrorMessage(errorMessage, (key) => t(key))
      })
    } finally {
      // Clean up abort controller if it's the current one
      if (useAskStore.getState().abortController === abortController) {
        useAskStore.getState().setAbortController(null)
      }
    }
  }, [t])

  const stopStreaming = useCallback(() => {
    const { abortController } = useAskStore.getState()
    if (abortController) {
      abortController.abort()
    }
    useAskStore.getState().setStreaming(false)
  }, [])

  return useMemo(() => ({
    isStreaming: store.isStreaming,
    strategy: store.strategy,
    answers: store.answers,
    finalAnswer: store.finalAnswer,
    error: store.error,
    sendAsk,
    reset: store.clearState,
    clearState: store.clearState,
    stopStreaming,
  }), [store.isStreaming, store.strategy, store.answers, store.finalAnswer, store.error, sendAsk, store.clearState, stopStreaming])
}
