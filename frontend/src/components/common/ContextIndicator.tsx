'use client'

import { FileText, Lightbulb, StickyNote } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/hooks/use-translation'

interface ContextIndicatorProps {
  sourcesInsights: number
  sourcesFull: number
  notesCount: number
  tokenCount?: number
  usedTokens?: number
  contextWindowTokens?: number
  estimated?: boolean
  className?: string
}

// Helper function to format large numbers with K/M suffixes
function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`
  }
  return num.toString()
}

function formatWindowTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1).replace(/\.0$/, '')}K`
  return String(value)
}

export function ContextIndicator({
  sourcesInsights,
  sourcesFull,
  notesCount,
  tokenCount,
  usedTokens,
  contextWindowTokens,
  estimated = true,
  className
}: ContextIndicatorProps) {
  const { t } = useTranslation()
  const hasContext = (sourcesInsights + sourcesFull) > 0 || notesCount > 0
  const rawPercent = usedTokens !== undefined && contextWindowTokens
    ? (usedTokens / contextWindowTokens) * 100
    : 0
  const progressPercent = Math.round(Math.min(100, Math.max(0, rawPercent)) * 100) / 100
  const displayPercent = Math.round(rawPercent)

  return (
    <div
      data-testid="context-summary"
      className={cn(
        'grid flex-shrink-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 border-t bg-muted/30 px-3 py-2 text-xs text-muted-foreground',
        className
      )}
    >
      <div data-testid="context-source-counts" className="flex min-w-0 items-center gap-1.5 justify-self-start">
        <span className="shrink-0 font-medium">{t.sources.contextLabel}</span>

        {hasContext ? (
          <div className="flex min-w-0 items-center gap-1">
            {sourcesInsights > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="outline" className="text-xs flex items-center gap-1 px-1.5 py-0.5 text-amber-600 border-amber-600/50 cursor-default">
                    <Lightbulb className="h-3 w-3" />
                    <span>{sourcesInsights}</span>
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t.sources.contextInsightsTooltip.replace('{count}', sourcesInsights.toString())}</p>
                </TooltipContent>
              </Tooltip>
            )}

            {sourcesFull > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="outline" className="text-xs flex items-center gap-1 px-1.5 py-0.5 text-primary border-primary/50 cursor-default">
                    <FileText className="h-3 w-3" />
                    <span>{sourcesFull}</span>
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t.sources.contextFullSourcesTooltip.replace('{count}', sourcesFull.toString())}</p>
                </TooltipContent>
              </Tooltip>
            )}

            {notesCount > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="outline" className="text-xs flex items-center gap-1 px-1.5 py-0.5 text-primary border-primary/50 cursor-default">
                    <StickyNote className="h-3 w-3" />
                    <span>{notesCount}</span>
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t.sources.contextFullNotesTooltip.replace('{count}', notesCount.toString())}</p>
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="tabular-nums">0</span>
            </TooltipTrigger>
            <TooltipContent>
              <p>{t.sources.contextNoContent}</p>
            </TooltipContent>
          </Tooltip>
        )}
      </div>

      <div data-testid="context-source-tokens" className="justify-self-center whitespace-nowrap tabular-nums">
        {t.sources.contextTokens.replace('{count}', formatNumber(tokenCount ?? 0))}
      </div>

      <div
        data-testid="context-window-usage"
        className="flex min-w-0 items-center justify-self-end gap-1.5 whitespace-nowrap tabular-nums"
      >
        {contextWindowTokens ? (
          <>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  {estimated && usedTokens !== undefined ? '≈' : ''}
                  {t.models.contextUsage
                    .replace('{used}', usedTokens === undefined ? '--' : formatWindowTokens(usedTokens))
                    .replace('{total}', formatWindowTokens(contextWindowTokens))}
                </span>
              </TooltipTrigger>
              {estimated && usedTokens !== undefined && (
                <TooltipContent>
                  <p>{t.models.contextEstimated}</p>
                </TooltipContent>
              )}
            </Tooltip>
            {usedTokens !== undefined && (
              <>
                <Progress
                  value={progressPercent}
                  aria-label={t.models.contextProgressLabel.replace('{percent}', String(displayPercent))}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progressPercent}
                  className="hidden h-1.5 w-12 sm:block lg:w-16"
                />
                <span>{t.models.contextPercent.replace('{percent}', String(displayPercent))}</span>
              </>
            )}
          </>
        ) : (
          <span className="truncate">{t.models.contextLimitUnknown}</span>
        )}
      </div>
    </div>
  )
}
