'use client'

import { useEffect, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  Square,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/lib/hooks/use-translation'
import {
  NotebookChatActivityStep,
  NotebookChatActivityTerminal,
  NotebookChatProgressStage,
} from '@/lib/chat/notebook-chat-activity'

interface ChatActivityFeedProps {
  steps: NotebookChatActivityStep[]
  elapsedSeconds: number
  terminal: NotebookChatActivityTerminal
}

export function ChatActivityFeed({
  steps,
  elapsedSeconds,
  terminal,
}: ChatActivityFeedProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(terminal === null)

  useEffect(() => {
    setExpanded(terminal === null)
  }, [terminal])

  if (steps.length === 0) return null

  const stageLabels: Record<NotebookChatProgressStage, string> = {
    received: t.chat.progressReceived,
    preparing_context: t.chat.progressPreparingContext,
    context_ready: t.chat.progressContextReady,
    planning: t.chat.progressPlanning,
    inspecting_scope: t.chat.progressInspectingScope,
    searching_notebook: t.chat.progressSearchingNotebook,
    reading_evidence: t.chat.progressReadingEvidence,
    searching_cross_notebook: t.chat.progressSearchingCrossNotebook,
    searching_web: t.chat.progressSearchingWeb,
    inspecting_scientific_databases: t.chat.progressInspectingScientificDatabases,
    searching_scientific_databases: t.chat.progressSearchingScientificDatabases,
    reading_scientific_record: t.chat.progressReadingScientificRecord,
    using_research_tool: t.chat.progressUsingResearchTool,
    awaiting_model: t.chat.progressAwaitingModel,
    synthesizing: t.chat.progressSynthesizing,
    model_streaming: t.chat.progressModelStreaming,
  }
  const completedCount = steps.filter(step => step.status === 'complete').length
  const summary = terminal === 'complete'
    ? t.chat.progressCompleteSummary
        .replace('{count}', String(completedCount))
        .replace('{seconds}', String(elapsedSeconds))
    : terminal === 'error'
      ? t.chat.progressErrorSummary.replace('{seconds}', String(elapsedSeconds))
      : terminal === 'cancelled'
        ? t.chat.progressCancelledSummary.replace('{seconds}', String(elapsedSeconds))
        : `${t.chat.progressWorking} (${elapsedSeconds}s)`

  return (
    <div
      data-testid="chat-activity-feed"
      className="max-w-2xl rounded-md border-l-2 border-primary/40 bg-muted/35 px-3 py-2"
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 w-full justify-start gap-2 px-0 text-xs font-medium hover:bg-transparent"
        onClick={() => setExpanded(value => !value)}
        aria-expanded={expanded}
        aria-label={expanded ? t.chat.progressCollapse : t.chat.progressExpand}
      >
        {terminal === 'complete' ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
        ) : terminal === 'error' ? (
          <AlertCircle className="h-3.5 w-3.5 text-destructive" />
        ) : terminal === 'cancelled' ? (
          <Square className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
        )}
        <span className="min-w-0 flex-1 truncate text-left">{summary}</span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </Button>

      {expanded && (
        <ol className="mt-1.5 space-y-1 border-t border-border/60 pt-2">
          {steps.map(step => (
            <li
              key={step.stage}
              data-status={step.status}
              className="flex min-h-5 items-center gap-2 text-xs text-muted-foreground"
            >
              {step.status === 'complete' ? (
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
              ) : step.status === 'error' ? (
                <AlertCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />
              ) : step.status === 'cancelled' ? (
                <Square className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              ) : (
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
              )}
              <span>{stageLabels[step.stage]}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
