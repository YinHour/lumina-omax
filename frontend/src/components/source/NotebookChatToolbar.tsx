'use client'

import { useState } from 'react'
import {
  Check,
  ChevronDown,
  CloudCheck,
  CloudOff,
  Download,
  FlaskConical,
  History,
  Loader2,
  MessageCircle,
  MessageSquare,
  Plus,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { BaseChatSession, NotebookChatMode, SourceChatMessage } from '@/lib/types/api'
import type { NotebookChatSaveStatus } from '@/lib/hooks/useNotebookChat'
import { useTranslation } from '@/lib/hooks/use-translation'
import { buildChatMarkdown, downloadChatMarkdown } from '@/lib/chat/export-chat-markdown'

interface NotebookChatToolbarProps {
  mode: NotebookChatMode
  onModeChange: (mode: NotebookChatMode) => void
  sessions: BaseChatSession[]
  currentSessionId?: string | null
  messages: SourceChatMessage[]
  saveStatus: NotebookChatSaveStatus
  disabled?: boolean
  onSelectSession: (sessionId: string) => void
  onStartNewSession: () => void
  onManageSessions: () => void
  onLoadExportMessages?: () => Promise<SourceChatMessage[]>
}

export function NotebookChatToolbar({
  mode,
  onModeChange,
  sessions,
  currentSessionId,
  messages,
  saveStatus,
  disabled = false,
  onSelectSession,
  onStartNewSession,
  onManageSessions,
  onLoadExportMessages,
}: NotebookChatToolbarProps) {
  const { t } = useTranslation()
  const currentSession = sessions.find(session => session.id === currentSessionId)
  const currentTitle = currentSession?.title || t.chat.newSession

  const [isExporting, setIsExporting] = useState(false)

  const handleExport = async () => {
    try {
      setIsExporting(true)
      const exportMessages = onLoadExportMessages
        ? await onLoadExportMessages()
        : messages
      const markdown = buildChatMarkdown({
        title: currentTitle,
        messages: exportMessages,
        exportedAt: new Date(),
        userLabel: t.chat.exportUserLabel,
        assistantLabel: t.chat.exportAssistantLabel,
      })
      downloadChatMarkdown(currentTitle, markdown)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
      <Tabs
        value={mode}
        onValueChange={value => onModeChange(value as NotebookChatMode)}
        className="min-w-0 gap-0"
      >
        <TabsList className="h-9">
          <TabsTrigger value="quick" disabled={disabled} className="h-7 px-3 text-xs">
            <MessageCircle />
            {t.chat.quickChat}
          </TabsTrigger>
          <TabsTrigger value="research" disabled={disabled} className="h-7 px-3 text-xs">
            <FlaskConical />
            {t.chat.researchAgent}
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="flex min-w-0 items-center gap-1.5">
        {saveStatus !== 'idle' && (
          <span
            data-testid="chat-save-status"
            className="hidden items-center gap-1 text-xs text-muted-foreground sm:inline-flex"
          >
            {saveStatus === 'saving' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : saveStatus === 'saved' ? (
              <CloudCheck className="h-3.5 w-3.5 text-emerald-600" />
            ) : (
              <CloudOff className="h-3.5 w-3.5 text-destructive" />
            )}
            {saveStatus === 'saving'
              ? t.chat.autoSaving
              : saveStatus === 'saved'
                ? t.chat.saved
                : t.chat.saveFailed}
          </span>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="max-w-48 min-w-0 gap-1.5"
              disabled={disabled}
              aria-label={t.chat.selectSession}
            >
              <MessageSquare className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate text-xs">{currentTitle}</span>
              <ChevronDown className="h-3.5 w-3.5 shrink-0" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72">
            <DropdownMenuLabel>{t.chat.sessions}</DropdownMenuLabel>
            {sessions.length === 0 ? (
              <DropdownMenuItem disabled>{t.chat.noSessions}</DropdownMenuItem>
            ) : (
              sessions.map(session => (
                <DropdownMenuItem
                  key={session.id}
                  onSelect={() => onSelectSession(session.id)}
                  className="justify-between"
                >
                  <span className="truncate">{session.title}</span>
                  {session.id === currentSessionId && <Check className="h-4 w-4 text-primary" />}
                </DropdownMenuItem>
              ))
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onManageSessions}>
              <History />
              {t.chat.manageSessions}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={handleExport} disabled={messages.length === 0 || isExporting}>
              {isExporting ? <Loader2 className="animate-spin" /> : <Download />}
              {t.chat.exportConversation}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={onStartNewSession}
              disabled={disabled}
              aria-label={t.chat.newSession}
            >
              <Plus />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t.chat.newSession}</TooltipContent>
        </Tooltip>
      </div>
    </div>
  )
}
