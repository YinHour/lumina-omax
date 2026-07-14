'use client'

import { Gauge } from 'lucide-react'
import { useTranslation } from '@/lib/hooks/use-translation'
import type { NotebookChatMode } from '@/lib/types/api'

interface ContextWindowMeterProps {
  mode: NotebookChatMode
  modelName?: string
}

export function ContextWindowMeter({
  mode,
  modelName,
}: ContextWindowMeterProps) {
  const { t } = useTranslation()

  if (!modelName || mode !== 'research') return null

  return (
    <div data-testid="context-window-meter" className="flex-shrink-0 border-t bg-muted/20 px-3 py-2">
      <div className="flex min-w-0 items-center gap-2 text-xs">
        <Gauge className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate font-medium" title={modelName}>{modelName}</span>
        <span className="text-muted-foreground">{t.models.contextOnDemand}</span>
      </div>
    </div>
  )
}
