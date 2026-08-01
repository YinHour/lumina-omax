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
  BuildContextResponse,
  NotebookChatMode,
  NotebookContextWindowUsage,
  NotebookChatStreamEvent,
  ResearchSkillMode,
} from '@/lib/types/api'
import { ContextSelections } from '@/app/(dashboard)/notebooks/[id]/page'
import { buildErrorBubbleBody } from '@/lib/chat/error-bubble'
import {
  NotebookChatActivityStep,
  NotebookChatActivityTerminal,
  NotebookChatProgressStage,
} from '@/lib/chat/notebook-chat-activity'

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

export type NotebookChatSaveStatus = 'idle' | 'saving' | 'saved' | 'error'

type ModeState<T> = Record<NotebookChatMode, T>

function isTransientNotebookMessage(message: NotebookChatMessage): boolean {
  return message.id.startsWith('temp-') || (
    message.id.startsWith('ai-') && !message.id.startsWith('ai-error-')
  )
}

export function useNotebookChat({ notebookId, sources, notes, contextSelections }: UseNotebookChatParams) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [chatMode, setChatModeState] = useState<NotebookChatMode>('quick')
  const [allowCrossNotebookDiscovery, setAllowCrossNotebookDiscovery] = useState(false)
  const [scientificDatabasesEnabled, setScientificDatabasesEnabled] = useState(false)
  const [researchSkillMode, setResearchSkillMode] = useState<ResearchSkillMode>('auto')
  const [selectedResearchSkillIds, setSelectedResearchSkillIds] = useState<string[]>([])
  const [currentSessionIds, setCurrentSessionIds] = useState<ModeState<string | null>>({
    quick: null,
    research: null,
  })
  const [newSessionDrafts, setNewSessionDrafts] = useState<ModeState<boolean>>({
    quick: false,
    research: false,
  })
  const [saveStatuses, setSaveStatuses] = useState<ModeState<NotebookChatSaveStatus>>({
    quick: 'idle',
    research: 'idle',
  })
  const currentSessionId = currentSessionIds[chatMode]
  const [messages, setMessages] = useState<NotebookChatMessage[]>([])
  const [hasMoreMessages, setHasMoreMessages] = useState(false)
  const [nextMessageCursor, setNextMessageCursor] = useState<number | null>(null)
  const [isLoadingEarlier, setIsLoadingEarlier] = useState(false)
  const messageSessionIdRef = useRef<string | null>(null)
  const loadedEarlierRef = useRef(false)
  const [suggestedQuestionsByMessageId, setSuggestedQuestionsByMessageId] = useState<Record<string, string[]>>({})
  const [isSending, setIsSending] = useState(false)
  const [activityStatus, setActivityStatus] = useState<NotebookChatActivityStatus | null>(null)
  const [activityElapsedSeconds, setActivityElapsedSeconds] = useState<number>(0)
  const [activitySteps, setActivitySteps] = useState<NotebookChatActivityStep[]>([])
  const [activityTerminal, setActivityTerminal] = useState<NotebookChatActivityTerminal>(null)
  const [activityMessageId, setActivityMessageId] = useState<string | null>(null)
  const [activityTotalElapsedSeconds, setActivityTotalElapsedSeconds] = useState(0)
  const [tokenCount, setTokenCount] = useState<number>(0)
  const [charCount, setCharCount] = useState<number>(0)
  const [contextWindowUsage, setContextWindowUsage] = useState<NotebookContextWindowUsage | null>(null)
  const isSendingRef = useRef(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const activityStartedAtRef = useRef<number | null>(null)
  const pendingSuggestedQuestionsRef = useRef<string[] | null>(null)
  const contextCacheRef = useRef<{ signature: string; response: BuildContextResponse } | null>(null)
  const contextRequestRef = useRef<{ signature: string; promise: Promise<BuildContextResponse> } | null>(null)
  // Pending model override for when user changes model before a session exists
  const [pendingModelOverrides, setPendingModelOverrides] = useState<ModeState<string | null>>(() => {
    if (typeof window !== 'undefined') {
      try {
        const savedByMode = localStorage.getItem('chat-model-overrides-by-mode')
        if (savedByMode) {
          return { quick: null, research: null, ...JSON.parse(savedByMode) }
        }
        const legacy = localStorage.getItem('chat-model-override')
        return { quick: legacy ? JSON.parse(legacy) : null, research: null }
      } catch {
        return { quick: null, research: null }
      }
    }
    return { quick: null, research: null }
  })
  const pendingModelOverride = pendingModelOverrides[chatMode]

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('chat-model-overrides-by-mode', JSON.stringify(pendingModelOverrides))
    }
  }, [pendingModelOverrides])

  const setSessionIdForMode = useCallback((mode: NotebookChatMode, sessionId: string | null) => {
    setCurrentSessionIds(previous => ({ ...previous, [mode]: sessionId }))
  }, [])

  const setSaveStatusForMode = useCallback((mode: NotebookChatMode, status: NotebookChatSaveStatus) => {
    setSaveStatuses(previous => ({ ...previous, [mode]: status }))
  }, [])

  useEffect(() => {
    if (!isSending || activityStartedAtRef.current === null) return

    const updateElapsed = () => {
      const startedAt = activityStartedAtRef.current
      if (startedAt !== null) {
        setActivityTotalElapsedSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
      }
    }

    updateElapsed()
    const intervalId = window.setInterval(updateElapsed, 1000)
    return () => window.clearInterval(intervalId)
  }, [isSending])

  const recordActivityStep = useCallback((
    stage: NotebookChatProgressStage,
    status: NotebookChatActivityStep['status'] = 'active'
  ) => {
    setActivitySteps(previous => {
      const next = previous.map(step =>
        step.status === 'active' && step.stage !== stage
          ? { ...step, status: 'complete' as const }
          : step
      )
      const existingIndex = next.findIndex(step => step.stage === stage)

      if (existingIndex === -1) {
        return [...next, { stage, status }]
      }

      next[existingIndex] = { ...next[existingIndex], status }
      return next
    })
  }, [])

  const finishActivity = useCallback((terminal: Exclude<NotebookChatActivityTerminal, null>) => {
    const terminalStepStatus: NotebookChatActivityStep['status'] = terminal === 'complete'
      ? 'complete'
      : terminal
    setActivitySteps(previous => previous.map(step => (
      step.status === 'active' ? { ...step, status: terminalStepStatus } : step
    )))
    const startedAt = activityStartedAtRef.current
    if (startedAt !== null) {
      const localElapsed = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
      setActivityTotalElapsedSeconds(previous => Math.max(previous, localElapsed))
    }
    setActivityTerminal(terminal)
  }, [])

  const resetActivity = useCallback(() => {
    activityStartedAtRef.current = null
    setActivitySteps([])
    setActivityTerminal(null)
    setActivityMessageId(null)
    setActivityTotalElapsedSeconds(0)
  }, [])

  // Fetch sessions for this notebook
  const {
    data: allSessions = [],
    isLoading: loadingSessions,
    refetch: refetchSessions
  } = useQuery({
    queryKey: QUERY_KEYS.notebookChatSessions(notebookId),
    queryFn: () => chatApi.listSessions(notebookId),
    enabled: !!notebookId
  })
  const sessions = allSessions.filter(
    session => (session.mode ?? 'quick') === chatMode
  )

  const { data: researchSkills = [] } = useQuery({
    queryKey: QUERY_KEYS.researchSkills,
    queryFn: chatApi.listResearchSkills,
    enabled: !!notebookId && chatMode === 'research',
  })

  const setResearchSkillSelection = useCallback((
    mode: ResearchSkillMode,
    selectedIds: string[]
  ) => {
    const knownIds = new Set(researchSkills.map(skill => skill.id))
    const safeIds = Array.from(new Set(selectedIds))
      .filter(id => knownIds.has(id))
      .slice(0, 3)
    setResearchSkillMode(mode === 'selected' && safeIds.length === 0 ? 'auto' : mode)
    setSelectedResearchSkillIds(mode === 'selected' ? safeIds : [])
  }, [researchSkills])

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
    if (
      currentSession?.messages &&
      (currentSession.mode ?? 'quick') === chatMode
    ) {
      const pendingSuggestedQuestions = pendingSuggestedQuestionsRef.current
      const persistedAiMessage = currentSession.messages
        .filter(msg => msg.type === 'ai')
        .at(-1)

      const sessionChanged = messageSessionIdRef.current !== currentSession.id
      messageSessionIdRef.current = currentSession.id
      setMessages(prev => {
        const transientMessages = prev.filter(isTransientNotebookMessage)
        if (sessionChanged) {
          return isSendingRef.current
            ? [...currentSession.messages, ...transientMessages]
            : currentSession.messages
        }

        const existingMessages = prev.filter(msg => !isTransientNotebookMessage(msg))
        const mergedById = new Map(
          [...existingMessages, ...currentSession.messages].map(message => [message.id, message])
        )
        const persistedMessages = Array.from(mergedById.values()).sort((left, right) => {
          if (left.sequence !== undefined && right.sequence !== undefined) {
            return left.sequence - right.sequence
          }
          return 0
        })
        if (!isSendingRef.current || transientMessages.length === 0) {
          return persistedMessages
        }

        const persistedIds = new Set(persistedMessages.map(msg => msg.id))
        const pendingMessages = transientMessages.filter(msg => !persistedIds.has(msg.id))
        return [...persistedMessages, ...pendingMessages]
      })

      if (sessionChanged || !loadedEarlierRef.current) {
        setHasMoreMessages(currentSession.has_more)
        setNextMessageCursor(currentSession.next_cursor ?? null)
        loadedEarlierRef.current = false
      }

      if (pendingSuggestedQuestions && persistedAiMessage) {
        const questions = pendingSuggestedQuestions
        setSuggestedQuestionsByMessageId(prev => ({
          ...prev,
          [persistedAiMessage.id]: questions,
        }))
        pendingSuggestedQuestionsRef.current = null
      }
    }
  }, [currentSession, chatMode])

  const loadEarlierMessages = useCallback(async () => {
    if (!currentSessionId || !hasMoreMessages || nextMessageCursor === null) return

    setIsLoadingEarlier(true)
    try {
      const page = await chatApi.getSession(currentSessionId, {
        limit: 50,
        before_sequence: nextMessageCursor,
      })
      setMessages(previous => {
        const knownIds = new Set(previous.map(message => message.id))
        const older = page.messages.filter(message => !knownIds.has(message.id))
        return [...older, ...previous]
      })
      loadedEarlierRef.current = true
      setHasMoreMessages(page.has_more)
      setNextMessageCursor(page.next_cursor ?? null)
    } finally {
      setIsLoadingEarlier(false)
    }
  }, [currentSessionId, hasMoreMessages, nextMessageCursor])

  const loadExportMessages = useCallback(async () => {
    if (!currentSessionId) return messages
    return chatApi.getAllSessionMessages(currentSessionId)
  }, [currentSessionId, messages])

  // Auto-select most recent session when sessions are loaded
  useEffect(() => {
    const currentBelongsToMode = sessions.some(session => session.id === currentSessionId)
    if (currentBelongsToMode && currentSessionId && newSessionDrafts[chatMode]) {
      setNewSessionDrafts(previous => ({ ...previous, [chatMode]: false }))
      return
    }
    if (sessions.length > 0 && !currentBelongsToMode && !newSessionDrafts[chatMode]) {
      // Sessions are sorted by created date desc from API
      const mostRecentSession = sessions[0]
      setSessionIdForMode(chatMode, mostRecentSession.id)
    }
  }, [sessions, currentSessionId, newSessionDrafts, chatMode, setSessionIdForMode])

  // Create session mutation
  const createSessionMutation = useMutation({
    mutationFn: (data: CreateNotebookChatSessionRequest) =>
      chatApi.createSession(data),
    onSuccess: (newSession) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.notebookChatSessions(notebookId)
      })
      const sessionMode = newSession.mode ?? 'quick'
      setSessionIdForMode(sessionMode, newSession.id)
      setNewSessionDrafts(previous => ({ ...previous, [sessionMode]: true }))
      setSaveStatusForMode(sessionMode, 'saved')
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
      const deletedMode = allSessions.find(session => session.id === deletedId)?.mode ?? chatMode
      if (currentSessionIds[deletedMode] === deletedId) {
        setSessionIdForMode(deletedMode, null)
        setSaveStatusForMode(deletedMode, 'idle')
      }
      if (currentSessionId === deletedId) {
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
    const requestResearchSkillMode = chatMode === 'research'
      ? researchSkillMode
      : 'off'
    const requestResearchSkillIds = requestResearchSkillMode === 'selected'
      ? selectedResearchSkillIds
      : []

    isSendingRef.current = true
    setIsSending(true)
    setSaveStatusForMode(chatMode, 'saving')
    setActivityStatus(chatMode === 'research' ? 'thinking' : 'gettingContext')
    setActivityElapsedSeconds(0)

    const userMessageId = `temp-${Date.now()}`
    activityStartedAtRef.current = Date.now()
    setActivityMessageId(userMessageId)
    setActivityTerminal(null)
    setActivityTotalElapsedSeconds(0)
    setActivitySteps([
      { stage: 'received', status: 'complete' },
      {
        stage: chatMode === 'research' ? 'planning' : 'preparing_context',
        status: 'active',
      },
    ])
    const userMessage: NotebookChatMessage = {
      id: userMessageId,
      type: 'human',
      content: trimmedMessage,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMessage])

    const preserveFailedUserMessage = () => {
      const failedUserMessageId = `failed-${userMessageId}`
      setMessages(previous => previous.map(item => (
        item.id === userMessageId
          ? { ...item, id: failedUserMessageId }
          : item
      )))
      setActivityMessageId(previous => (
        previous === userMessageId ? failedUserMessageId : previous
      ))
    }

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
            mode: chatMode,
            // Include pending model override when creating session
            model_override: pendingModelOverride ?? undefined
          })
          sessionId = newSession.id
          messageSessionIdRef.current = sessionId
          setSessionIdForMode(chatMode, sessionId)
          // Clear pending model override now that it's applied to the session
          setPendingModelOverrides(previous => ({ ...previous, [chatMode]: null }))
          queryClient.invalidateQueries({
            queryKey: QUERY_KEYS.notebookChatSessions(notebookId)
          })
        } catch (err: unknown) {
          const error = err as { response?: { data?: { detail?: string } }, message?: string };
          toast.error(getApiErrorMessage(error.response?.data?.detail || error.message, (key) => t(key), 'apiErrors.failedToCreateSession'))
          finishActivity('error')
          setSaveStatusForMode(chatMode, 'error')
          setMessages(prev => prev.filter(msg => msg.id !== userMessageId))
          return
        }
      }

      const context = chatMode === 'quick'
        ? await buildContext()
        : { sources: [], notes: [] }
      if (chatMode === 'quick') {
        recordActivityStep('preparing_context', 'complete')
        recordActivityStep('context_ready', 'complete')
        recordActivityStep(enableWebSearch ? 'searching_web' : 'awaiting_model')
      }
      setActivityStatus(enableWebSearch ? 'searchingWeb' : 'awaitingModel')
      setActivityElapsedSeconds(0)
      
      // Create abort controller for cancellation
      abortController = new AbortController()
      abortControllerRef.current = abortController

      // Start streaming request
      const response = chatMode === 'research'
        ? await chatApi.sendResearchMessage({
            session_id: sessionId,
            message: trimmedMessage,
            model_override: modelOverride ?? (currentSession?.model_override ?? undefined),
            enable_web_search: enableWebSearch,
            allow_cross_notebook_discovery: allowCrossNotebookDiscovery,
            enable_scientific_databases: scientificDatabasesEnabled,
            research_skill_mode: requestResearchSkillMode,
            research_skill_ids: requestResearchSkillIds,
          }, abortController.signal)
        : await chatApi.sendMessage({
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
      let activityTerminalReached = false
      let transcriptSaveStatus: Extract<NotebookChatSaveStatus, 'saved' | 'error'> | null = null
      let buffer = ''
      const markAnswerComplete = (terminal: Exclude<NotebookChatActivityTerminal, null> = 'complete') => {
        activityTerminalReached = true
        finishActivity(terminal)
        isSendingRef.current = false
        setActivityStatus(null)
        setActivityElapsedSeconds(0)
        setIsSending(false)
        setSaveStatusForMode(
          chatMode,
          terminal === 'complete' ? (transcriptSaveStatus ?? 'saved') : 'error'
        )
      }

      const handleStreamEvent = (data: NotebookChatStreamEvent) => {
        if (data.type === 'ai_message') {
          if (!aiMessage) {
            setActivityStatus('modelStreaming')
            setActivityElapsedSeconds(0)
            recordActivityStep('model_streaming')
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
        } else if (data.type === 'reasoning_status') {
          setActivityStatus('thinking')
          setActivityElapsedSeconds(0)
          recordActivityStep('synthesizing')
        } else if (data.type === 'chat_status') {
          const validStages: NotebookChatProgressStage[] = [
            'received',
            'preparing_context',
            'context_ready',
            'planning',
            'inspecting_scope',
            'searching_notebook',
            'reading_evidence',
            'searching_cross_notebook',
            'searching_web',
            'inspecting_scientific_databases',
            'searching_scientific_databases',
            'reading_scientific_record',
            'loading_research_skills',
            'using_research_tool',
            'awaiting_model',
            'synthesizing',
            'model_streaming',
          ]
          if (
            data.stage &&
            validStages.includes(data.stage as NotebookChatProgressStage) &&
            (data.status === 'active' || data.status === 'complete')
          ) {
            recordActivityStep(
              data.stage as NotebookChatProgressStage,
              data.status
            )
          }
        } else if (data.type === 'heartbeat') {
          if (typeof data.elapsed_ms === 'number') {
            const elapsedSeconds = Math.max(1, Math.floor(data.elapsed_ms / 1000))
            setActivityElapsedSeconds(elapsedSeconds)
            setActivityTotalElapsedSeconds(previous => Math.max(previous, elapsedSeconds))
          }
        } else if (
          data.type === 'context_usage' &&
          typeof data.model_id === 'string' &&
          typeof data.model_name === 'string' &&
          typeof data.provider === 'string' &&
          typeof data.input_tokens === 'number'
        ) {
          setContextWindowUsage({
            model_id: data.model_id,
            model_name: data.model_name,
            provider: data.provider,
            input_tokens: data.input_tokens,
            context_window_tokens: data.context_window_tokens,
            context_window_source: data.context_window_source,
            estimated: data.estimated !== false,
          })
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
        } else if (
          data.type === 'transcript_status' &&
          (data.status === 'saved' || data.status === 'error')
        ) {
          transcriptSaveStatus = data.status
          setSaveStatusForMode(chatMode, data.status)
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

          preserveFailedUserMessage()

          if (!aiMessage) {
            aiMessage = {
              id: `ai-error-${Date.now()}`,
              type: 'ai',
              content: bubbleBody,
              timestamp: new Date().toISOString(),
            }
            setMessages(prev => [...prev, aiMessage!])
          } else {
            const previousAiMessageId = aiMessage.id
            aiMessage = {
              ...aiMessage,
              id: previousAiMessageId.startsWith('ai-error-')
                ? previousAiMessageId
                : `ai-error-${Date.now()}`,
              content: `${aiMessage.content}\n\n${bubbleBody}`,
            }
            setMessages(prev =>
              prev.map(msg => msg.id === previousAiMessageId
                ? aiMessage!
                : msg
              )
            )
          }
          inlineStreamError = true
          markAnswerComplete('error')
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

      if (!activityTerminalReached && !abortController.signal.aborted) {
        markAnswerComplete()
      }

      // Refetch current session to get updated data and persistence. Skip
      // this when the stream ended with an inline error (e.g. llm_timeout):
      // that bubble lives only in front-end state, and reloading the
      // persisted session would overwrite it with the empty/last-known
      // server state.
      if (!inlineStreamError && transcriptSaveStatus !== 'error') {
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
        finishActivity('cancelled')
        setSaveStatusForMode(chatMode, 'error')
        return
      }
      // Genuine transport-layer failures (e.g. Next.js proxy reset, network
      // dropped before SSE was established) still surface as a toast — the
      // server never had a chance to emit an `error` event. All SSE-signaled
      // errors are rendered inline as AI bubbles in `handleStreamEvent`.
      const error = err as { response?: { data?: { detail?: string } }, message?: string };
      console.error('Error sending message:', error)
      finishActivity('error')
      setSaveStatusForMode(chatMode, 'error')
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
      if (requestResearchSkillMode === 'selected') {
        setResearchSkillMode('auto')
        setSelectedResearchSkillIds([])
      }
    }
  }, [
    notebookId,
    chatMode,
    allowCrossNotebookDiscovery,
    scientificDatabasesEnabled,
    researchSkillMode,
    selectedResearchSkillIds,
    currentSessionId,
    currentSession,
    pendingModelOverride,
    buildContext,
    refetchCurrentSession,
    queryClient,
    t,
    finishActivity,
    recordActivityStep,
    setSaveStatusForMode,
    setSessionIdForMode,
  ])

  const cancelStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      isSendingRef.current = false
      finishActivity('cancelled')
      setSaveStatusForMode(chatMode, 'error')
      setActivityStatus(null)
      setActivityElapsedSeconds(0)
      setIsSending(false)
    }
  }, [finishActivity, chatMode, setSaveStatusForMode])

  const sendSuggestedQuestion = useCallback((question: string, modelOverride?: string, enableWebSearch?: boolean) => {
    return sendMessage(question, modelOverride, enableWebSearch)
  }, [sendMessage])

  // Switch session
  const switchSession = useCallback((sessionId: string) => {
    resetActivity()
    messageSessionIdRef.current = null
    loadedEarlierRef.current = false
    setHasMoreMessages(false)
    setNextMessageCursor(null)
    setNewSessionDrafts(previous => ({ ...previous, [chatMode]: false }))
    setSaveStatusForMode(chatMode, 'saved')
    setSuggestedQuestionsByMessageId({})
    setContextWindowUsage(null)
    setSessionIdForMode(chatMode, sessionId)
  }, [resetActivity, chatMode, setSaveStatusForMode, setSessionIdForMode])

  const startNewSession = useCallback(() => {
    if (isSendingRef.current) return
    resetActivity()
    setNewSessionDrafts(previous => ({ ...previous, [chatMode]: true }))
    setSaveStatusForMode(chatMode, 'idle')
    setSuggestedQuestionsByMessageId({})
    setContextWindowUsage(null)
    setSessionIdForMode(chatMode, null)
    setMessages([])
    messageSessionIdRef.current = null
    loadedEarlierRef.current = false
    setHasMoreMessages(false)
    setNextMessageCursor(null)
    if (chatMode === 'research') {
      setAllowCrossNotebookDiscovery(false)
      setScientificDatabasesEnabled(false)
      setResearchSkillMode('auto')
      setSelectedResearchSkillIds([])
    }
  }, [resetActivity, chatMode, setSaveStatusForMode, setSessionIdForMode])

  // Create session
  const createSession = useCallback((title?: string) => {
    return createSessionMutation.mutate({
      notebook_id: notebookId,
      title,
      mode: chatMode,
    })
  }, [createSessionMutation, notebookId, chatMode])

  const setChatMode = useCallback((mode: NotebookChatMode) => {
    if (isSendingRef.current || mode === chatMode) return
    resetActivity()
    setChatModeState(mode)
    if (mode === 'research') {
      setAllowCrossNotebookDiscovery(false)
      setScientificDatabasesEnabled(false)
      setResearchSkillMode('auto')
      setSelectedResearchSkillIds([])
    }
    setSuggestedQuestionsByMessageId({})
    setContextWindowUsage(null)
    setMessages([])
    messageSessionIdRef.current = null
    loadedEarlierRef.current = false
    setHasMoreMessages(false)
    setNextMessageCursor(null)
  }, [chatMode, resetActivity])

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
      setPendingModelOverrides(previous => ({ ...previous, [chatMode]: model }))
    }
  }, [currentSessionId, updateSessionMutation, chatMode])

  // Update token/char counts when context selections change
  useEffect(() => {
    if (chatMode !== 'quick') {
      setTokenCount(0)
      setCharCount(0)
      return
    }
    const updateContextCounts = async () => {
      try {
        await buildContext()
      } catch (error) {
        console.error('Error updating context counts:', error)
      }
    }
    updateContextCounts()
  }, [buildContext, chatMode])

  return {
    // State
    sessions,
    currentSession: currentSession && (currentSession.mode ?? 'quick') === chatMode
      ? currentSession
      : sessions.find(s => s.id === currentSessionId),
    currentSessionId,
    currentSessionIds,
    messages,
    hasMoreMessages,
    isLoadingEarlier,
    suggestedQuestionsByMessageId,
    isSending,
    activityStatus,
    activityElapsedSeconds,
    activitySteps,
    activityTerminal,
    activityMessageId,
    activityTotalElapsedSeconds,
    loadingSessions,
    tokenCount,
    charCount,
    contextWindowUsage,
    pendingModelOverride,
    saveStatus: saveStatuses[chatMode],
    chatMode,
    allowCrossNotebookDiscovery,
    scientificDatabasesEnabled,
    researchSkills,
    researchSkillMode,
    selectedResearchSkillIds,

    // Actions
    createSession,
    updateSession,
    deleteSession,
    switchSession,
    startNewSession,
    sendMessage,
    sendSuggestedQuestion,
    cancelStreaming,
    setModelOverride,
    setChatMode,
    setAllowCrossNotebookDiscovery,
    setScientificDatabasesEnabled,
    setResearchSkillSelection,
    loadEarlierMessages,
    loadExportMessages,
    refetchSessions
  }
}
