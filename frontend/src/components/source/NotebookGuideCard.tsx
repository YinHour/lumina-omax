'use client'

import { Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { NotebookGuideResponse } from '@/lib/types/api'
import { useTranslation } from '@/lib/hooks/use-translation'
import { SuggestedQuestionList } from './SuggestedQuestionList'

interface NotebookGuideCardProps {
  title?: string
  guide: NotebookGuideResponse
  disabled?: boolean
  onQuestionClick: (question: string) => void
  onSaveSummary?: () => void
  onRegenerate?: () => void
}

export function NotebookGuideCard({
  title,
  guide,
  disabled = false,
  onQuestionClick,
  onSaveSummary,
  onRegenerate,
}: NotebookGuideCardProps) {
  const { t } = useTranslation()
  const generatedDate = guide.generated_at
    ? new Date(guide.generated_at).toLocaleDateString()
    : null

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center py-8">
      <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Sparkles className="h-6 w-6" />
      </div>

      <div className="mb-6 space-y-2 text-center">
        {title && <h2 className="text-xl font-semibold text-foreground">{title}</h2>}
        <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">
            {t.chat.sourceCount.replace('{count}', guide.source_count.toString())}
          </Badge>
          {generatedDate && <span>{generatedDate}</span>}
        </div>
      </div>

      <Card className="w-full border-border/80 bg-card/80 shadow-sm">
        <CardContent className="space-y-5 p-5">
          <p className="text-sm leading-7 text-muted-foreground">
            {guide.summary}
          </p>

          <div className="flex flex-wrap gap-2">
            {onSaveSummary && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={disabled}
                onClick={onSaveSummary}
              >
                {t.chat.saveSummaryToNote}
              </Button>
            )}
            {onRegenerate && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={disabled}
                onClick={onRegenerate}
              >
                {t.chat.regenerateGuide}
              </Button>
            )}
          </div>

          <SuggestedQuestionList
            questions={guide.questions}
            disabled={disabled}
            onQuestionClick={onQuestionClick}
          />
        </CardContent>
      </Card>
    </div>
  )
}
