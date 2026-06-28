'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/lib/hooks/use-toast'
import { getApiErrorMessage } from '@/lib/utils/error-handler'
import { useTranslation } from '@/lib/hooks/use-translation'
import { chatApi } from '@/lib/api/chat'
import { QUERY_KEYS } from '@/lib/api/query-client'
import {
  NotebookChatMessage,
  CreateNotebookChatSessionRequest,
  UpdateNotebookChatSessionRequest,
  SourceListResponse,
  NoteResponse,
  BuildContextResponse
} from '@/lib/types/api'
import { ContextSelections } from '@/app/(dashboard)/notebooks/[id]/page'
import { buildErrorBubbleBody } from '@/lib/chat/error-bubble'

interface UseNotebookChatParams {
  notebookId: string
  sources: SourceListResponse[]
  notes: NoteResponse[]
  contextSelections: ContextSelections
}

export type NotebookChatActivityStatus =
  | 'gettingContext'
  | 'searchingWeb'
  | 'thinking'
  | 'awaitingModel'
  | 'modelStreaming'


export function useNotebookChat({ notebookId, sources, notes, contextSelections }: UseNotebookChatParams) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<NotebookChatMessage[]>([])
  const [suggestedQuestionsByMessageId, setSuggestedQuestionsByMessageId] = useState<Record<string, string[]>>({})
  const [isSending, setIsSending] = useState(false)
  const [activityStatus, setActivityStatus] = useState<NotebookChatActivityStatus | null>(null)
  const [activityElapsedSeconds, setActivityElapsedSeconds] = useState<number>(0)
  const [tokenCount, setTokenCount] = useState<number>(0)
  const [charCount, setCharCount] = useState<number>(0)
  const isSendingRef = useRef(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const pendingSuggestedQuestionsRef = useRef<string[] | null>(null)
  const contextCacheRef = useRef<{ signature: string; response: BuildContextResponse } | null>(null)
  const contextRequestRef = useRef<{ signature: string; promise: Promise<BuildContextResponse> } | null>(null)
  // Pending model override for when user changes model before a session exists
  const [pendingModelOverride, setPendingModelOverride] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('chat-model-override')
        return saved ? JSON.parse(saved) : null
      } catch {
        return null
      }
    }
    return null
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('chat-model-override', JSON.stringify(pendingModelOverride))
    }
  }, [pendingModelOverride])

  // Fetch sessions for this notebook
  const {
    data: sessions = [],
    isLoading: loadingSessions,
    refetch: refetchSessions
  } = useQuery({
    queryKey: QUERY_KEYS.notebookChatSessions(notebookId),
    queryFn: () => chatApi.listSessions(notebookId),
    enabled: !!notebookId
  })

  // Fetch current session with messages
  const {
    data: currentSession,
    refetch: refetchCurrentSession
  } = useQuery({
    queryKey: QUERY_KEYS.notebookChatSession(currentSessionId!),
    queryFn: () => chatApi.getSession(currentSessionId!),
    enabled: !!notebookId && !!currentSessionId
  })

  // Update messages when current session changes
  useEffect(() => {
    if (currentSession?.messages) {
      const pendingSuggestedQuestions = pendingSuggestedQuestionsRef.current
      const persistedAiMessage = currentSession.messages
        .filter(msg => msg.type === 'ai')
        .at(-1)

      setMessages(prev => {
        const optimisticMessages = prev.filter(msg => msg.id.startsWith('temp-'))
        if (!isSendingRef.current || optimisticMessages.length === 0) {
          return currentSession.messages
        }

        const persistedIds = new Set(currentSession.messages.map(msg => msg.id))
        const pendingMessages = optimisticMessages.filter(msg => !persistedIds.has(msg.id))
        return [...currentSession.messages, ...pendingMessages]
      })

      if (pendingSuggestedQuestions && persistedAiMessage) {
        const questions = pendingSuggestedQuestions
        setSuggestedQuestionsByMessageId(prev => ({
          ...prev,
          [persistedAiMessage.id]: questions,
        }))
        pendingSuggestedQuestionsRef.current = null
      }
    }
  }, [currentSession])

  // Auto-select most recent session when sessions are loaded
  useEffect(() => {
    if (sessions.length > 0 && !currentSessionId) {
      // Sessions are sorted by created date desc from API
      const mostRecentSession = sessions[0]
      setCurrentSessionId(mostRecentSession.id)
    }
  }, [sessions, currentSessionId])

  // Create session mutation
  const createSessionMutation = useMutation({
    mutationFn: (data: CreateNotebookChatSessionRequest) =>
      chatApi.createSession(data),
    onSuccess: (newSession) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.notebookChatSessions(notebookId)
      })
      setCurrentSessionId(newSession.id)
      toast.success(t.chat.sessionCreated)
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } }, message?: string };
      toast.error(getApiErrorMessage(error.response?.data?.detail || error.message, (key) => t(key), 'apiErrors.failedToCreateSession'))
    }
  })

  // Update session mutation
  const updateSessionMutation = useMutation({
    mutationFn: ({ sessionId, data }: {
      sessionId: string
      data: UpdateNotebookChatSessionRequest
    }) => chatApi.updateSession(sessionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.notebookChatSessions(notebookId)
      })
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.notebookChatSession(currentSessionId!)
      })
      toast.success(t.chat.sessionUpdated)
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } }, message?: string };
      toast.error(getApiErrorMessage(error.response?.data?.detail || error.message, (key) => t(key), 'apiErrors.failedToUpdateSession'))
    }
  })

  // Delete session mutation
  const deleteSessionMutation = useMutation({
    mutationFn: (sessionId: string) =>
      chatApi.deleteSession(sessionId),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.notebookChatSessions(notebookId)
      })
      if (currentSessionId === deletedId) {
        setCurrentSessionId(null)
        setMessages([])
      }
      toast.success(t.chat.sessionDeleted)
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } }, message?: string };
      toast.error(getApiErrorMessage(error.response?.data?.detail || error.message, (key) => t(key), 'apiErrors.failedToDeleteSession'))
    }
  })

  // Build context from sources and notes based on user selections
  const buildContext = useCallback(async () => {
    // Build context_config mapping IDs to selection modes
    const context_config: { sources: Record<string, string>, notes: Record<string, string> } = {
      sources: {},
      notes: {}
    }

    // Map source selections
    sources.forEach(source => {
      const mode = contextSelections.sources[source.id]
      if (mode === 'insights') {
        context_config.sources[source.id] = 'insights'
      } else if (mode === 'full') {
        context_config.sources[source.id] = 'full content'
      } else {
        context_config.sources[source.id] = 'not in'
      }
    })

    // Map note selections
    notes.forEach(note => {
      const mode = contextSelections.notes[note.id]
      if (mode === 'full') {
        context_config.notes[note.id] = 'full content'
      } else {
        context_config.notes[note.id] = 'not in'
      }
    })

    const signature = JSON.stringify({
      notebookId,
      sources: sources
        .map(source => [
          source.id,
          source.updated,
          context_config.sources[source.id],
        ])
        .sort((a, b) => String(a[0]).localeCompare(String(b[0]))),
      notes: notes
        .map(note => [
          note.id,
          note.updated,
          context_config.notes[note.id],
        ])
        .sort((a, b) => String(a[0]).localeCompare(String(b[0]))),
    })

    const cached = contextCacheRef.current
    if (cached?.signature === signature) {
      setTokenCount(cached.response.token_count)
      setCharCount(cached.response.char_count)
      return cached.response.context
    }

    const pending = contextRequestRef.current
    if (pending?.signature === signature) {
      const response = await pending.promise
      setTokenCount(response.token_count)
      setCharCount(response.char_count)
      return response.context
    }

    // Call API to build context with actual content
    const request = chatApi.buildContext({
      notebook_id: notebookId,
      context_config
    })
    contextRequestRef.current = { signature, promise: request }

    try {
      const response = await request
      contextCacheRef.current = { signature, response }

      // Store token and char counts
      setTokenCount(response.token_count)
      setCharCount(response.char_count)

      return response.context
    } finally {
      if (contextRequestRef.current?.promise === request) {
        contextRequestRef.current = null
      }
    }
  }, [notebookId, sources, notes, contextSelections])

  // Send message (with streaming)
  const sendMessage = useCallback(async (message: string, modelOverride?: string, enableWebSearch?: boolean) => {
    const trimmedMessage = message.trim()
    if (!trimmedMessage || isSendingRef.current) {
      return
    }

    isSendingRef.current = true
    setIsSending(true)
    setActivityStatus('gettingContext')
    setActivityElapsedSeconds(0)

    const userMessageId = `temp-${Date.now()}`
    const userMessage: NotebookChatMessage = {
      id: userMessageId,
      type: 'human',
      content: trimmedMessage,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMessage])

    let abortController: AbortController | null = null
    try {
      let sessionId = currentSessionId

      // Auto-create session if none exists
      if (!sessionId) {
        try {
          const defaultTitle = trimmedMessage.length > 30
            ? `${trimmedMessage.substring(0, 30)}...`
            : trimmedMessage
          const newSession = await chatApi.createSession({
            notebook_id: notebookId,
            title: defaultTitle,
            // Include pending model override when creating session
            model_override: pendingModelOverride ?? undefined
          })
          sessionId = newSession.id
          setCurrentSessionId(sessionId)
          // Clear pending model override now that it's applied to the session
          setPendingModelOverride(null)
          queryClient.invalidateQueries({
            queryKey: QUERY_KEYS.notebookChatSessions(notebookId)
          })
        } catch (err: unknown) {
          const error = err as { response?: { data?: { detail?: string } }, message?: string };
          toast.error(getApiErrorMessage(error.response?.data?.detail || error.message, (key) => t(key), 'apiErrors.failedToCreateSession'))
          setMessages(prev => prev.filter(msg => msg.id !== userMessageId))
          return
        }
      }

      // Build context
      const context = await buildContext()
      setActivityStatus(enableWebSearch ? 'searchingWeb' : 'awaitingModel')
      setActivityElapsedSeconds(0)
      
      // Create abort controller for cancellation
      abortController = new AbortController()
      abortControllerRef.current = abortController

      // Start streaming request
      const response = await chatApi.sendMessage({
        session_id: sessionId,
        message: trimmedMessage,
        context,
        model_override: modelOverride ?? (currentSession?.model_override ?? undefined),
        enable_web_search: enableWebSearch
      }, abortController.signal)

      if (!response) {
        throw new Error('No response body')
      }

      const reader = response.getReader()
      const decoder = new TextDecoder()
      let aiMessage: NotebookChatMessage | null = null
      let pendingSuggestedQuestions: string[] | null = null
      let inlineStreamError = false
      let buffer = ''
      const markAnswerComplete = () => {
        isSendingRef.current = false
        setActivityStatus(null)
        setActivityElapsedSeconds(0)
        setIsSending(false)
      }

      const handleStreamEvent = (data: { type?: string; content?: string; message?: string; questions?: unknown; stage?: string; elapsed_ms?: number; error_code?: string; timeout_seconds?: number }) => {
        if (data.type === 'ai_message') {
          if (!aiMessage) {
            setActivityStatus('modelStreaming')
            setActivityElapsedSeconds(0)
          }
          if (!aiMessage) {
            aiMessage = {
              id: `ai-${Date.now()}`,
              type: 'ai',
              content: data.content || '',
              timestamp: new Date().toISOString()
            }
            setMessages(prev => [...prev, aiMessage!])
          } else {
            aiMessage.content += data.content || ''
            setMessages(prev =>
              prev.map(msg => msg.id === aiMessage!.id
                ? { ...msg, content: aiMessage!.content }
                : msg
              )
            )
          }
        } else if (data.type === 'heartbeat') {
          // Backend keep-alive while waiting for first model byte. Surface elapsed
          // seconds so the UI can show "model still working, waited Ns".
          if (data.stage === 'awaiting_model' && typeof data.elapsed_ms === 'number') {
            setActivityStatus('awaitingModel')
            setActivityElapsedSeconds(Math.max(1, Math.floor(data.elapsed_ms / 1000)))
          }
        } else if (data.type === 'suggested_questions') {
          const questions = Array.isArray(data.questions)
            ? data.questions.filter((question): question is string => typeof question === 'string' && question.trim().length > 0).slice(0, 3)
            : []
          if (aiMessage && questions.length > 0) {
            pendingSuggestedQuestions = questions
            pendingSuggestedQuestionsRef.current = questions
            setSuggestedQuestionsByMessageId(prev => ({
              ...prev,
              [aiMessage!.id]: questions,
            }))
          }
        } else if (data.type === 'answer_complete') {
          markAnswerComplete()
        } else if (data.type === 'error') {
          // All chat SSE errors render as an inline AI-role bubble (see §29.7
          // and §31). Bubble layout is shared with source chat / ask via
          // `buildErrorBubbleBody`.
          const { body: bubbleBody } = buildErrorBubbleBody(data, {
            errorLlmTimeoutPrefix: t.chat.errorLlmTimeoutPrefix,
            errorLlmTimeout: t.chat.errorLlmTimeoutNotebook,
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

          if (!aiMessage) {
            aiMessage = {
              id: `ai-error-${Date.now()}`,
              type: 'ai',
              content: bubbleBody,
              timestamp: new Date().toISOString(),
            }
            setMessages(prev => [...prev, aiMessage!])
          } else {
            aiMessage.content += `\n\n${bubbleBody}`
            setMessages(prev =>
              prev.map(msg => msg.id === aiMessage!.id
                ? { ...msg, content: aiMessage!.content }
                : msg
              )
            )
          }
          inlineStreamError = true
          markAnswerComplete()
          return
        }
      }

      while (true) {
        if (!abortController || abortController.signal.aborted) break

        const { done, value } = await reader.read()
        if (done) {
          // Process any remaining data in buffer
          if (buffer) {
            const lines = buffer.split('\n')
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6))
                  handleStreamEvent(data)
                } catch {}
              }
            }
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        
        let newlineIndex
        while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
          const line = buffer.slice(0, newlineIndex)
          buffer = buffer.slice(newlineIndex + 1)
          
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              handleStreamEvent(data)
            } catch (e) {
              if (e instanceof SyntaxError) {
                console.error('Error parsing SSE data:', e, 'Line:', line)
              } else {
                throw e
              }
            }
          }
        }
      }

      // Refetch current session to get updated data and persistence. Skip
      // this when the stream ended with an inline error (e.g. llm_timeout):
      // that bubble lives only in front-end state, and reloading the
      // persisted session would overwrite it with the empty/last-known
      // server state.
      if (!inlineStreamError) {
        const refetchResult = await refetchCurrentSession()
        let persistedMessages = refetchResult.data?.messages
        if (!persistedMessages && pendingSuggestedQuestions) {
          const refreshedSession = await chatApi.getSession(sessionId)
          queryClient.setQueryData(QUERY_KEYS.notebookChatSession(sessionId), refreshedSession)
          persistedMessages = refreshedSession.messages
        }
        const persistedAiMessage = persistedMessages
          ?.filter(msg => msg.type === 'ai')
          .at(-1)
        if (pendingSuggestedQuestions && persistedAiMessage) {
          const questions = pendingSuggestedQuestions
          setSuggestedQuestionsByMessageId(prev => ({
            ...prev,
            [persistedAiMessage.id]: questions,
          }))
          pendingSuggestedQuestionsRef.current = null
        }
      }
    } catch (err: unknown) {
      // AbortError is user-initiated cancellation, not a real error
      if (err instanceof DOMException && err.name === 'AbortError') {
        return
      }
      // Genuine transport-layer failures (e.g. Next.js proxy reset, network
      // dropped before SSE was established) still surface as a toast — the
      // server never had a chance to emit an `error` event. All SSE-signaled
      // errors are rendered inline as AI bubbles in `handleStreamEvent`.
      const error = err as { response?: { data?: { detail?: string } }, message?: string };
      console.error('Error sending message:', error)
      toast.error(getApiErrorMessage(error.response?.data?.detail || error.message, (key) => t(key), 'apiErrors.failedToSendMessage'))
      // Remove optimistic message on error
      setMessages(prev => prev.filter(msg => !msg.id.startsWith('temp-')))
    } finally {
      isSendingRef.current = false
      setActivityStatus(null)
      setActivityElapsedSeconds(0)
      setIsSending(false)
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null
      }
    }
  }, [
    notebookId,
    currentSessionId,
    currentSession,
    pendingModelOverride,
    buildContext,
    refetchCurrentSession,
    queryClient,
    t
  ])

  const cancelStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      isSendingRef.current = false
      setActivityStatus(null)
      setActivityElapsedSeconds(0)
      setIsSending(false)
    }
  }, [])

  const sendSuggestedQuestion = useCallback((question: string, modelOverride?: string, enableWebSearch?: boolean) => {
    return sendMessage(question, modelOverride, enableWebSearch)
  }, [sendMessage])

  // Switch session
  const switchSession = useCallback((sessionId: string) => {
    setSuggestedQuestionsByMessageId({})
    setCurrentSessionId(sessionId)
  }, [])

  // Create session
  const createSession = useCallback((title?: string) => {
    return createSessionMutation.mutate({
      notebook_id: notebookId,
      title
    })
  }, [createSessionMutation, notebookId])

  // Update session
  const updateSession = useCallback((sessionId: string, data: UpdateNotebookChatSessionRequest) => {
    return updateSessionMutation.mutate({
      sessionId,
      data
    })
  }, [updateSessionMutation])

  // Delete session
  const deleteSession = useCallback((sessionId: string) => {
    return deleteSessionMutation.mutate(sessionId)
  }, [deleteSessionMutation])

  // Set model override - handles both existing sessions and pending state
  const setModelOverride = useCallback((model: string | null) => {
    if (currentSessionId) {
      // Session exists - update it directly
      updateSessionMutation.mutate({
        sessionId: currentSessionId,
        data: { model_override: model }
      })
    } else {
      // No session yet - store as pending
      setPendingModelOverride(model)
    }
  }, [currentSessionId, updateSessionMutation])

  // Update token/char counts when context selections change
  useEffect(() => {
    const updateContextCounts = async () => {
      try {
        await buildContext()
      } catch (error) {
        console.error('Error updating context counts:', error)
      }
    }
    updateContextCounts()
  }, [buildContext])

  return {
    // State
    sessions,
    currentSession: currentSession || sessions.find(s => s.id === currentSessionId),
    currentSessionId,
    messages,
    suggestedQuestionsByMessageId,
    isSending,
    activityStatus,
    activityElapsedSeconds,
    loadingSessions,
    tokenCount,
    charCount,
    pendingModelOverride,

    // Actions
    createSession,
    updateSession,
    deleteSession,
    switchSession,
    sendMessage,
    sendSuggestedQuestion,
    cancelStreaming,
    setModelOverride,
    refetchSessions
  }
}
