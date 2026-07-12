'use client'

import { useState, useRef, useEffect, useId } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Checkbox } from '@/components/ui/checkbox'
import { Bot, User, Send, Loader2, Square, FileText, Lightbulb, StickyNote, Clock, Globe, PencilLine } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import {
  SourceChatMessage,
  SourceChatContextIndicator,
  BaseChatSession,
  NotebookGuideResponse,
  NotebookChatMode,
} from '@/lib/types/api'
import { ModelSelector } from './ModelSelector'
import { ContextIndicator } from '@/components/common/ContextIndicator'
import { SessionManager } from '@/components/source/SessionManager'
import { MessageActions } from '@/components/source/MessageActions'
import {
  convertReferencesToCompactMarkdown,
  createCompactReferenceCodeComponent,
  createCompactReferenceLinkComponent,
  ensureNumberedWebBibliographySection
} from '@/lib/utils/source-references'
import { useModalManager } from '@/lib/hooks/use-modal-manager'
import { toast } from '@/lib/hooks/use-toast'
import { useTranslation } from '@/lib/hooks/use-translation'
import { NotebookGuideCard } from './NotebookGuideCard'
import { SuggestedQuestionList } from './SuggestedQuestionList'
import { stripThinkingContent } from '@/lib/chat/thinking-content'
import { ChatActivityFeed } from './ChatActivityFeed'
import {
  NotebookChatActivityStep,
  NotebookChatActivityTerminal,
} from '@/lib/chat/notebook-chat-activity'
import { NotebookChatToolbar } from './NotebookChatToolbar'
import type { NotebookChatSaveStatus } from '@/lib/hooks/useNotebookChat'

type ChatActivityStatus =
  | 'gettingContext'
  | 'searchingWeb'
  | 'thinking'
  | 'awaitingModel'
  | 'modelStreaming'

interface NotebookContextStats {
  sourcesInsights: number
  sourcesFull: number
  notesCount: number
  tokenCount?: number
  charCount?: number
}

interface ChatPanelProps {
  messages: SourceChatMessage[]
  isStreaming: boolean
  contextIndicators: SourceChatContextIndicator | null
  onSendMessage: (message: string, modelOverride?: string, enableWebSearch?: boolean) => void
  modelOverride?: string
  onModelChange?: (model?: string) => void
  // Session management props
  sessions?: BaseChatSession[]
  currentSessionId?: string | null
  onCreateSession?: (title: string) => void
  onStartNewSession?: () => void
  onSelectSession?: (sessionId: string) => void
  onDeleteSession?: (sessionId: string) => void
  onUpdateSession?: (sessionId: string, title: string) => void
  loadingSessions?: boolean
  // Generic props for reusability
  title?: string
  contextType?: 'source' | 'notebook'
  // Notebook context stats (for notebook chat)
  notebookContextStats?: NotebookContextStats
  // Notebook ID for saving notes
  notebookId?: string
  // Cancel streaming
  onCancelStreaming?: () => void
  notebookGuide?: NotebookGuideResponse | null
  isGuideLoading?: boolean
  suggestedQuestionsByMessageId?: Record<string, string[]>
  activityStatus?: ChatActivityStatus | null
  activityElapsedSeconds?: number
  activitySteps?: NotebookChatActivityStep[]
  activityTerminal?: NotebookChatActivityTerminal
  activityMessageId?: string | null
  activityTotalElapsedSeconds?: number
  onRegenerateGuide?: () => void
  chatMode?: NotebookChatMode
  onChatModeChange?: (mode: NotebookChatMode) => void
  allowCrossNotebookDiscovery?: boolean
  onAllowCrossNotebookDiscoveryChange?: (enabled: boolean) => void
  saveStatus?: NotebookChatSaveStatus
  hasMoreMessages?: boolean
  isLoadingEarlier?: boolean
  onLoadEarlierMessages?: () => Promise<void>
  onLoadExportMessages?: () => Promise<SourceChatMessage[]>
}

export function ChatPanel({
  messages,
  isStreaming,
  contextIndicators,
  onSendMessage,
  modelOverride,
  onModelChange,
  sessions = [],
  currentSessionId,
  onCreateSession,
  onStartNewSession,
  onSelectSession,
  onDeleteSession,
  onUpdateSession,
  loadingSessions = false,
  title,
  contextType = 'source',
  notebookContextStats,
  notebookId,
  onCancelStreaming,
  notebookGuide,
  isGuideLoading = false,
  suggestedQuestionsByMessageId = {},
  activityStatus,
  activityElapsedSeconds,
  activitySteps = [],
  activityTerminal = null,
  activityMessageId,
  activityTotalElapsedSeconds = 0,
  onRegenerateGuide,
  chatMode = 'quick',
  onChatModeChange,
  allowCrossNotebookDiscovery = false,
  onAllowCrossNotebookDiscoveryChange,
  saveStatus = 'idle',
  hasMoreMessages = false,
  isLoadingEarlier = false,
  onLoadEarlierMessages,
  onLoadExportMessages,
}: ChatPanelProps) {
  const { t } = useTranslation()
  const chatInputId = useId()
  const [sourceInput, setSourceInput] = useState('')
  const [notebookDrafts, setNotebookDrafts] = useState<Record<NotebookChatMode, string>>({
    quick: '',
    research: '',
  })
  const input = contextType === 'notebook' ? notebookDrafts[chatMode] : sourceInput
  const setInput = (value: string) => {
    if (contextType === 'notebook') {
      setNotebookDrafts(previous => ({ ...previous, [chatMode]: value }))
    } else {
      setSourceInput(value)
    }
  }

  const [webSearchByScope, setWebSearchByScope] = useState<Record<'source' | NotebookChatMode, boolean>>(() => {
    if (typeof window !== 'undefined') {
      try {
        const legacy = localStorage.getItem('chat-web-search-enabled')
        const legacyValue = legacy ? JSON.parse(legacy) : false
        const read = (key: string, fallback: boolean) => {
          const saved = localStorage.getItem(key)
          return saved ? JSON.parse(saved) : fallback
        }
        return {
          source: read('chat-web-search-enabled-source', legacyValue),
          quick: read('chat-web-search-enabled-quick', legacyValue),
          research: read('chat-web-search-enabled-research', false),
        }
      } catch {
        return { source: false, quick: false, research: false }
      }
    }
    return { source: false, quick: false, research: false }
  })
  const webSearchScope: 'source' | NotebookChatMode = contextType === 'notebook'
    ? chatMode
    : 'source'
  const webSearchEnabled = webSearchByScope[webSearchScope]
  const setWebSearchEnabled = (enabled: boolean) => {
    setWebSearchByScope(previous => ({ ...previous, [webSearchScope]: enabled }))
  }

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('chat-web-search-enabled-source', JSON.stringify(webSearchByScope.source))
      localStorage.setItem('chat-web-search-enabled-quick', JSON.stringify(webSearchByScope.quick))
      localStorage.setItem('chat-web-search-enabled-research', JSON.stringify(webSearchByScope.research))
    }
  }, [webSearchByScope])
  
  const [sessionManagerOpen, setSessionManagerOpen] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const { openModal } = useModalManager()

  const handleCrossNotebookChange = (enabled: boolean) => {
    onAllowCrossNotebookDiscoveryChange?.(enabled)
  }

  const handleReferenceClick = (type: string, id: string) => {
    const modalType = type === 'source_insight' ? 'insight' : type as 'source' | 'note' | 'insight'

    try {
      openModal(modalType, id)
      // Note: The modal system uses URL parameters and doesn't throw errors for missing items.
      // The modal component itself will handle displaying "not found" states.
      // This try-catch is here for future enhancements or unexpected errors.
    } catch {
      toast.error(t.common.noResults)
    }
  }

  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true)
  const lastMessageCount = useRef(messages.length)
  const isUserScrolling = useRef(false)
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Auto-scroll to bottom when new messages arrive, but only if user hasn't scrolled up
  useEffect(() => {
    // If a new message was added (either by user or AI starting to respond), 
    // force auto-scroll back on, UNLESS the user is actively scrolling up
    if (messages.length > lastMessageCount.current && !isUserScrolling.current) {
      setIsAutoScrollEnabled(true)
    }
    lastMessageCount.current = messages.length

    if (isAutoScrollEnabled) {
      // Clear any existing timeout
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current)
      }
      
      // Use requestAnimationFrame for smoother scrolling during React renders
      scrollTimeoutRef.current = setTimeout(() => {
        requestAnimationFrame(() => {
          if (scrollAreaRef.current) {
            const viewport = scrollAreaRef.current.querySelector('[data-slot="scroll-area-viewport"]')
            if (viewport) {
              viewport.scrollTop = viewport.scrollHeight
            } else {
              messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
            }
          } else {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
          }
        })
      }, 10)
      
      return () => {
        if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current)
      }
    }
  }, [messages, isAutoScrollEnabled]) // Removed isStreaming from dependencies to avoid jitter

  // Detect when user scrolls up to disable auto-scroll
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement
    // Check if we are near the bottom (within 150px to be safe, increased threshold for smoother detection)
    const isNearBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 150
    
    // Only update if the user has intentionally scrolled away from the bottom
    // We don't want to disable auto-scroll just because a new message pushed the content down
    if (!isNearBottom && isAutoScrollEnabled) {
      isUserScrolling.current = true
      setIsAutoScrollEnabled(false)
    } else if (isNearBottom && !isAutoScrollEnabled) {
      // User scrolled back to bottom manually
      isUserScrolling.current = false
      setIsAutoScrollEnabled(true)
    }
  }

  const sendMessageNow = (message: string) => {
    const trimmed = message.trim()
    if (trimmed && !isStreaming) {
      setIsAutoScrollEnabled(true)
      isUserScrolling.current = false
      // Force scroll immediately on send
      if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current)
      scrollTimeoutRef.current = setTimeout(() => {
        requestAnimationFrame(() => {
          if (scrollAreaRef.current) {
            const viewport = scrollAreaRef.current.querySelector('[data-slot="scroll-area-viewport"]')
            if (viewport) {
              viewport.scrollTop = viewport.scrollHeight
            } else {
              messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
            }
          } else {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
          }
        })
      }, 10)
      onSendMessage(trimmed, modelOverride, webSearchEnabled)
    }
  }

  // Re-enable auto-scroll when user sends a new message
  const handleSend = () => {
    if (input.trim() && !isStreaming) {
      sendMessageNow(input)
      setInput('')
    }
  }

  const handleSuggestedQuestionClick = (question: string) => {
    sendMessageNow(question)
  }

  const handleLoadEarlier = async () => {
    if (!onLoadEarlierMessages || isLoadingEarlier) return
    const viewport = scrollAreaRef.current?.querySelector<HTMLElement>(
      '[data-slot="scroll-area-viewport"]'
    )
    const previousHeight = viewport?.scrollHeight ?? 0
    const previousTop = viewport?.scrollTop ?? 0
    await onLoadEarlierMessages()
    requestAnimationFrame(() => {
      if (viewport) {
        viewport.scrollTop = previousTop + viewport.scrollHeight - previousHeight
      }
    })
  }

  const handleEditHumanMessage = (message: string) => {
    setInput(message)
    requestAnimationFrame(() => {
      inputRef.current?.focus()
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Detect platform for correct modifier key
    const isMac = typeof navigator !== 'undefined' && navigator.userAgent.toUpperCase().indexOf('MAC') >= 0
    const isModifierPressed = isMac ? e.metaKey : e.ctrlKey

    if (e.key === 'Enter' && isModifierPressed) {
      e.preventDefault()
      handleSend()
    }
  }

  // Detect platform for placeholder text
  const isMac = typeof navigator !== 'undefined' && navigator.userAgent.toUpperCase().indexOf('MAC') >= 0
  const keyHint = isMac ? '⌘+Enter' : 'Ctrl+Enter'
  const shouldShowActivityStatus = Boolean(
    isStreaming &&
    activityStatus &&
    activitySteps.length === 0 &&
    messages[messages.length - 1]?.type === 'human'
  )
  const resolvedActivityMessageId = messages.some(message => message.id === activityMessageId)
    ? activityMessageId
    : [...messages].reverse().find(message => message.type === 'human')?.id
  const activityStatusLabel = activityStatus
    ? (() => {
        const labelMap: Record<ChatActivityStatus, string> = {
          gettingContext: t.chat.activityGettingContext,
          searchingWeb: t.chat.activitySearchingWeb,
          thinking: t.chat.activityThinking,
          awaitingModel: t.chat.activityAwaitingModel,
          modelStreaming: t.chat.activityModelStreaming,
        }
        const base = labelMap[activityStatus]
        if (
          activityStatus === 'awaitingModel' &&
          typeof activityElapsedSeconds === 'number' &&
          activityElapsedSeconds > 0
        ) {
          return `${base}（${activityElapsedSeconds}s）`
        }
        return base
      })()
    : null

  return (
    <>
    <Card className="flex flex-col h-full flex-1 overflow-hidden">
      <CardHeader className="pb-3 flex-shrink-0">
        {contextType === 'notebook' && onChatModeChange && onSelectSession && onStartNewSession ? (
          <NotebookChatToolbar
            mode={chatMode}
            onModeChange={onChatModeChange}
            sessions={sessions}
            currentSessionId={currentSessionId}
            messages={messages}
            saveStatus={saveStatus}
            disabled={isStreaming || loadingSessions}
            onSelectSession={onSelectSession}
            onStartNewSession={onStartNewSession}
            onManageSessions={() => setSessionManagerOpen(true)}
            onLoadExportMessages={onLoadExportMessages}
          />
        ) : (
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              {title || t.chat.chatWith.replace('{name}', t.navigation.sources)}
            </CardTitle>
            {onSelectSession && onCreateSession && onDeleteSession && (
              <Button
                variant="ghost"
                size="sm"
                className="gap-2"
                onClick={() => setSessionManagerOpen(true)}
                disabled={loadingSessions}
              >
                <Clock className="h-4 w-4" />
                <span className="text-xs">{t.chat.sessions}</span>
              </Button>
            )}
          </div>
        )}

        {onSelectSession && (onCreateSession || onStartNewSession) && onDeleteSession && (
            <Dialog open={sessionManagerOpen} onOpenChange={setSessionManagerOpen}>
              <DialogContent className="sm:max-w-[420px] p-0 overflow-hidden">
                <DialogTitle className="sr-only">{t.chat.sessionsTitle}</DialogTitle>
                <SessionManager
                  sessions={sessions}
                  currentSessionId={currentSessionId ?? null}
                  onCreateSession={onCreateSession}
                  onStartNewSession={onStartNewSession ? () => {
                    onStartNewSession()
                    setSessionManagerOpen(false)
                  } : undefined}
                  onSelectSession={(sessionId) => {
                    onSelectSession(sessionId)
                    setSessionManagerOpen(false)
                  }}
                  onUpdateSession={(sessionId, title) => onUpdateSession?.(sessionId, title)}
                  onDeleteSession={(sessionId) => onDeleteSession?.(sessionId)}
                  loadingSessions={loadingSessions}
                />
              </DialogContent>
            </Dialog>
        )}
      </CardHeader>
      <CardContent className="flex-1 flex flex-col min-h-0 p-0">
        <ScrollArea 
          className="flex-1 min-h-0 px-4"
          viewportClassName="[&>div]:!block"
          ref={scrollAreaRef}
          onScrollCapture={handleScroll}
        >
          <div className="space-y-4 py-4">
            {contextType === 'notebook' && hasMoreMessages && onLoadEarlierMessages && (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleLoadEarlier}
                  disabled={isLoadingEarlier}
                  className="gap-2 text-xs text-muted-foreground"
                >
                  {isLoadingEarlier && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  {isLoadingEarlier ? t.chat.loadingEarlierMessages : t.chat.loadEarlierMessages}
                </Button>
              </div>
            )}
            {notebookGuide?.status === 'ready' && notebookGuide.summary && (
              <NotebookGuideCard
                title={title}
                guide={notebookGuide}
                disabled={isStreaming}
                onQuestionClick={handleSuggestedQuestionClick}
                onRegenerate={onRegenerateGuide}
              />
            )}
            {contextType === 'notebook' && isGuideLoading && !notebookGuide?.summary && (
              <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 rounded-lg border bg-muted/30 p-5">
                <div className="flex items-center gap-3">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  <div>
                    <p className="text-sm font-medium">{t.chat.generatingGuide}</p>
                    <p className="text-xs text-muted-foreground">{t.chat.generatingGuideDesc}</p>
                  </div>
                </div>
                <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                  <span>{t.chat.guideStepReading}</span>
                  <span>{t.chat.guideStepSummarizing}</span>
                  <span>{t.chat.guideStepQuestions}</span>
                </div>
              </div>
            )}

            {messages.length === 0 ? (
              !notebookGuide?.summary && !isGuideLoading && (
                <div className="text-center text-muted-foreground py-8">
                  <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-sm">
                    {t.chat.startConversation.replace('{type}', contextType === 'source' ? t.navigation.sources : t.common.notebook)}
                  </p>
                  <p className="text-xs mt-2">{t.chat.askQuestions}</p>
                </div>
              )
            ) : (
              messages.map((message) => (
                <div key={message.id} className="space-y-2">
                <div
                  className={`flex gap-3 ${
                    message.type === 'human' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  {message.type === 'ai' && (
                    <div className="flex-shrink-0">
                      <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                        <Bot className="h-4 w-4" />
                      </div>
                    </div>
                  )}
                  <div className="flex flex-col gap-2 max-w-[80%]">
                    <div
                      className={`rounded-lg px-4 py-2 ${
                        message.type === 'human'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      {message.type === 'ai' ? (
                        <AIMessageContent
                          content={message.content}
                          onReferenceClick={handleReferenceClick}
                        />
                      ) : (
                        <p className="text-sm break-all">{message.content}</p>
                      )}
                    </div>
                    {message.type === 'ai' && (
                      <MessageActions
                        content={message.content}
                        notebookId={notebookId}
                      />
                    )}
                    {message.type === 'ai' && suggestedQuestionsByMessageId[message.id]?.length > 0 && (
                      <SuggestedQuestionList
                        questions={suggestedQuestionsByMessageId[message.id]}
                        disabled={isStreaming}
                        onQuestionClick={handleSuggestedQuestionClick}
                      />
                    )}
                    {message.type === 'human' && (
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                          disabled={isStreaming}
                          onClick={() => handleEditHumanMessage(message.content)}
                          aria-label={t.chat.editAndAskAgain}
                        >
                          <PencilLine className="h-3.5 w-3.5" />
                          {t.chat.editAndAskAgain}
                        </Button>
                      </div>
                    )}
                  </div>
                  {message.type === 'human' && (
                    <div className="flex-shrink-0">
                      <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                        <User className="h-4 w-4 text-primary-foreground" />
                      </div>
                    </div>
                  )}
                </div>
                {message.type === 'human' && message.id === resolvedActivityMessageId && activitySteps.length > 0 && (
                  <div className="px-11">
                    <ChatActivityFeed
                      steps={activitySteps}
                      elapsedSeconds={activityTotalElapsedSeconds}
                      terminal={activityTerminal}
                    />
                  </div>
                )}
                </div>
              ))
            )}
            {shouldShowActivityStatus && activityStatusLabel && (
              <div className="flex justify-start pl-10">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>{activityStatusLabel}</span>
                </div>
              </div>
            )}
            {isStreaming && !onCancelStreaming && !activityStatus && (
              <div className="flex justify-start pl-10">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Context Indicators */}
        {contextIndicators && (
          <div className="border-t px-4 py-2">
            <div className="flex flex-wrap gap-2 text-xs">
              {contextIndicators.sources?.length > 0 && (
                <Badge variant="outline" className="gap-1">
                  <FileText className="h-3 w-3" />
                  {contextIndicators.sources.length} {t.navigation.sources}
                </Badge>
              )}
              {contextIndicators.insights?.length > 0 && (
                <Badge variant="outline" className="gap-1">
                  <Lightbulb className="h-3 w-3" />
                  {contextIndicators.insights.length} {contextIndicators.insights.length === 1 ? t.common.insight : t.common.insights}
                </Badge>
              )}
              {contextIndicators.notes?.length > 0 && (
                <Badge variant="outline" className="gap-1">
                  <StickyNote className="h-3 w-3" />
                  {contextIndicators.notes.length} {contextIndicators.notes.length === 1 ? t.common.note : t.common.notes}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Notebook Context Indicator */}
        {notebookContextStats && (
          <ContextIndicator
            sourcesInsights={notebookContextStats.sourcesInsights}
            sourcesFull={notebookContextStats.sourcesFull}
            notesCount={notebookContextStats.notesCount}
            tokenCount={notebookContextStats.tokenCount}
            charCount={notebookContextStats.charCount}
          />
        )}

        {/* Input Area */}
        <div className="flex-shrink-0 p-4 space-y-3 border-t">
          {/* Settings row */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div data-testid="chat-options-row" className="flex flex-wrap items-center gap-x-2 gap-y-2">
              <label
                htmlFor={`${chatInputId}-web-search`}
                className="inline-flex h-8 cursor-pointer items-center gap-2 rounded-md px-2 text-xs text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
              >
                <Checkbox
                  id={`${chatInputId}-web-search`}
                  checked={webSearchEnabled}
                  onCheckedChange={(checked) => setWebSearchEnabled(checked === true)}
                  disabled={isStreaming}
                />
                <Globe className="h-3.5 w-3.5" />
                {t.settings.webSearch}
              </label>

              {contextType === 'notebook' && chatMode === 'research' && onAllowCrossNotebookDiscoveryChange && (
                    <label
                      htmlFor={`${chatInputId}-cross-notebook`}
                      className="inline-flex h-8 cursor-pointer items-center gap-2 rounded-md px-2 text-xs text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                    >
                      <Checkbox
                        id={`${chatInputId}-cross-notebook`}
                        checked={allowCrossNotebookDiscovery}
                        onCheckedChange={(checked) => handleCrossNotebookChange(checked === true)}
                        disabled={isStreaming}
                      />
                      {t.chat.crossNotebookDiscovery}
                    </label>
              )}
            </div>

            {onModelChange && (
              <ModelSelector
                currentModel={modelOverride}
                onModelChange={onModelChange}
                disabled={isStreaming}
              />
            )}
          </div>

          <div className="flex gap-2 items-end min-w-0">
            <Textarea
              ref={inputRef}
              id={chatInputId}
              name="chat-message"
              autoComplete="off"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`${t.chat.sendPlaceholder} (${t.chat.pressToSend.replace('{key}', keyHint)})`}
              disabled={isStreaming}
              className="flex-1 min-h-[40px] max-h-[100px] resize-none py-2 px-3 min-w-0"
              rows={1}
            />
            <Button
              onClick={isStreaming && onCancelStreaming ? onCancelStreaming : handleSend}
              disabled={!isStreaming && !input.trim()}
              size="icon"
              className={`h-[40px] w-[40px] flex-shrink-0 ${isStreaming && onCancelStreaming ? 'bg-destructive hover:bg-destructive/90' : ''}`}
              aria-label={isStreaming && onCancelStreaming ? t.chat.stopGenerating : t.chat.sendPlaceholder}
            >
              {isStreaming && onCancelStreaming ? (
                <Square className="h-4 w-4" />
              ) : isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>

    </>
  )
}

// Helper component to render AI messages with clickable references
function AIMessageContent({
  content,
  onReferenceClick
}: {
  content: string
  onReferenceClick: (type: string, id: string) => void
}) {
  const { t } = useTranslation()
  const visibleContent = stripThinkingContent(content)
  // Ensure ## 参考文献 / ## Web References lists are ordered (1. 2. …) when the model omits numbers
  const withNumberedBibliography = ensureNumberedWebBibliographySection(visibleContent)
  const markdownWithCompactRefs = convertReferencesToCompactMarkdown(
    withNumberedBibliography,
    t.common.workspaceReferences
  )

  // Create custom link component for compact references
  const LinkComponent = createCompactReferenceLinkComponent(onReferenceClick)
  const CodeComponent = createCompactReferenceCodeComponent(onReferenceClick)

  return (
    <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none break-words prose-headings:font-semibold prose-a:text-blue-600 prose-a:break-all prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-p:mb-4 prose-p:leading-7 prose-li:mb-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          a: LinkComponent,
          code: CodeComponent,
          p: ({ children }) => <p className="mb-4">{children}</p>,
          h1: ({ children }) => <h1 className="mb-4 mt-6">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-3 mt-5">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-3 mt-4">{children}</h3>,
          h4: ({ children }) => <h4 className="mb-2 mt-4">{children}</h4>,
          h5: ({ children }) => <h5 className="mb-2 mt-3">{children}</h5>,
          h6: ({ children }) => <h6 className="mb-2 mt-3">{children}</h6>,
          li: ({ children }) => <li className="mb-1 pl-0.5">{children}</li>,
          ul: ({ children }) => <ul className="mb-4 list-disc space-y-1 pl-6 [list-style-position:outside]">{children}</ul>,
          ol: ({ children }) => (
            <ol className="mb-4 list-decimal space-y-1 pl-6 [list-style-position:outside] marker:text-foreground">
              {children}
            </ol>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto">
              <table className="min-w-full border-collapse border border-border">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-muted">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-border">{children}</tr>,
          th: ({ children }) => <th className="border border-border px-3 py-2 text-left font-semibold">{children}</th>,
          td: ({ children }) => <td className="border border-border px-3 py-2">{children}</td>,
        }}
      >
        {markdownWithCompactRefs}
      </ReactMarkdown>
    </div>
  )
}
