'use client'

import { useCallback, useMemo } from 'react'
import { toast } from '@/lib/hooks/use-toast'
import { useTranslation } from '@/lib/hooks/use-translation'
import { getApiErrorMessage } from '@/lib/utils/error-handler'
import { searchApi } from '@/lib/api/search'
import { AskStreamEvent } from '@/lib/types/search'
import { useAskStore } from '@/lib/stores/ask-store'
import { buildErrorBubbleBody } from '@/lib/chat/error-bubble'

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
    useAskStore.getState().setActivityElapsedSeconds(0)
    useAskStore.getState().setErrorBubble(null)

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
              } else if (data.type === 'coverage') {
                useAskStore.getState().setCoverage({
                  total_sources: data.total_sources || 0,
                  embedded_sources: data.embedded_sources || 0,
                  retrieved_sources: data.retrieved_sources || 0,
                  retrieved_source_ids: data.retrieved_source_ids || [],
                })
              } else if (data.type === 'heartbeat') {
                // Silence-based keep-alive while ask phases are running. The
                // store-level seconds counter is consumed by StreamingResponse
                // to render "still working, waited Ns".
                if (typeof data.elapsed_ms === 'number') {
                  useAskStore.getState().setActivityElapsedSeconds(
                    Math.max(1, Math.floor(data.elapsed_ms / 1000)),
                  )
                }
              } else if (data.type === 'complete') {
                if (data.coverage) {
                  useAskStore.getState().setCoverage(data.coverage)
                }
                const finalAnswer = data.final_answer || useAskStore.getState().finalAnswer || ''
                if (finalAnswer.trim()) {
                  useAskStore.getState().addHistoryEntry({
                    question,
                    answer: finalAnswer,
                    coverage: data.coverage || useAskStore.getState().coverage,
                  })
                }
                useAskStore.getState().setStreaming(false)
                useAskStore.getState().setActivityElapsedSeconds(0)
              } else if (data.type === 'error') {
                // §32: render Ask SSE errors as an inline notice (markdown
                // bubble body) so user can read guidance + diagnostic block,
                // mirroring chat. Stored on `errorBubble`; the page renders
                // it instead of the previous one-shot toast.
                const { body } = buildErrorBubbleBody(data, {
                  errorLlmTimeoutPrefix: t.chat.errorLlmTimeoutPrefix,
                  errorLlmTimeout: t.chat.errorLlmTimeoutAsk,
                  errorAuthentication: t.chat.errorAuthentication,
                  errorRateLimit: t.chat.errorRateLimit,
                  errorConfiguration: t.chat.errorConfiguration,
                  errorNetwork: t.chat.errorNetwork,
                  errorExternalService: t.chat.errorExternalService,
                  errorInvalidInput: t.chat.errorInvalidInput,
                  errorNotFound: t.chat.errorNotFound,
                  errorInternal: t.chat.errorInternal,
                  errorGeneric: t.chat.errorGeneric,
                })
                useAskStore.getState().setErrorBubble(body)
                useAskStore.getState().setStreaming(false)
                useAskStore.getState().setActivityElapsedSeconds(0)
                // Do not throw — we want the bubble to be rendered, not a toast.
                return
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
      useAskStore.getState().setActivityElapsedSeconds(0)

    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Ask request aborted')
        return
      }

      // Transport-layer failure (server never had a chance to emit an SSE
      // error event). SSE-signaled errors are rendered inline via the
      // store's errorBubble, not as a toast.
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred'
      console.error('Ask error:', error)

      useAskStore.getState().setError(errorMessage)
      useAskStore.getState().setActivityElapsedSeconds(0)

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
    useAskStore.getState().setActivityElapsedSeconds(0)
  }, [])

  return useMemo(() => ({
    isStreaming: store.isStreaming,
    strategy: store.strategy,
    answers: store.answers,
    finalAnswer: store.finalAnswer,
    coverage: store.coverage,
    history: store.history,
    error: store.error,
    errorBubble: store.errorBubble,
    activityElapsedSeconds: store.activityElapsedSeconds,
    sendAsk,
    reset: store.clearState,
    clearState: store.clearState,
    restoreHistoryEntry: store.restoreHistoryEntry,
    clearHistory: store.clearHistory,
    stopStreaming,
  }), [
    store.isStreaming,
    store.strategy,
    store.answers,
    store.finalAnswer,
    store.coverage,
    store.history,
    store.error,
    store.errorBubble,
    store.activityElapsedSeconds,
    sendAsk,
    store.clearState,
    store.restoreHistoryEntry,
    store.clearHistory,
    stopStreaming,
  ])
}
