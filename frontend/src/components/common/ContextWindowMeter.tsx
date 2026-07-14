'use client'

import { Gauge } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import { useTranslation } from '@/lib/hooks/use-translation'
import type { NotebookChatMode } from '@/lib/types/api'

interface ContextWindowMeterProps {
  mode: NotebookChatMode
  modelName?: string
  usedTokens?: number
  contextWindowTokens?: number
  estimated?: boolean
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1).replace(/\.0$/, '')}K`
  return String(value)
}

export function ContextWindowMeter({
  mode,
  modelName,
  usedTokens,
  contextWindowTokens,
  estimated = true,
}: ContextWindowMeterProps) {
  const { t } = useTranslation()

  if (!modelName) return null

  if (mode === 'research') {
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

  const rawPercent = usedTokens !== undefined && contextWindowTokens
    ? (usedTokens / contextWindowTokens) * 100
    : 0
  const progressPercent = Math.min(100, Math.max(0, rawPercent))
  const displayPercent = Math.round(rawPercent)

  return (
    <div data-testid="context-window-meter" className="flex-shrink-0 space-y-1.5 border-t bg-muted/20 px-3 py-2">
      <div className="flex min-w-0 items-center justify-between gap-3 text-xs">
        <div className="flex min-w-0 items-center gap-2">
          <Gauge className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="truncate font-medium" title={modelName}>{modelName}</span>
          {estimated && usedTokens !== undefined && (
            <span className="shrink-0 text-muted-foreground">{t.models.contextEstimated}</span>
          )}
        </div>
        {contextWindowTokens ? (
          <span className="shrink-0 tabular-nums text-muted-foreground">
            {t.models.contextUsage
              .replace('{used}', usedTokens === undefined ? '--' : formatTokens(usedTokens))
              .replace('{total}', formatTokens(contextWindowTokens))}
            {usedTokens !== undefined && ` · ${t.models.contextPercent.replace('{percent}', String(displayPercent))}`}
          </span>
        ) : (
          <span className="shrink-0 text-muted-foreground">{t.models.contextLimitUnknown}</span>
        )}
      </div>
      {contextWindowTokens ? (
        <Progress
          value={progressPercent}
          aria-label={t.models.contextProgressLabel.replace('{percent}', String(displayPercent))}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progressPercent}
          className="h-1.5"
        />
      ) : null}
      {contextWindowTokens && usedTokens === undefined && (
        <p className="text-[11px] text-muted-foreground">{t.models.contextPending}</p>
      )}
    </div>
  )
}
