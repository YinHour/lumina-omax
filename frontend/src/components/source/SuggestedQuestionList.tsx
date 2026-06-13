'use client'

import { Button } from '@/components/ui/button'
import { useTranslation } from '@/lib/hooks/use-translation'

interface SuggestedQuestionListProps {
  questions: string[]
  disabled?: boolean
  onQuestionClick: (question: string) => void
}

export function SuggestedQuestionList({
  questions,
  disabled = false,
  onQuestionClick,
}: SuggestedQuestionListProps) {
  const { t } = useTranslation()
  const visibleQuestions = questions.filter(Boolean).slice(0, 3)

  if (visibleQuestions.length === 0) {
    return null
  }

  return (
    <div className="space-y-2" aria-label={t.chat.suggestedNextSteps}>
      <p className="text-xs font-medium text-muted-foreground">
        {t.chat.suggestedNextSteps}
      </p>
      <div className="space-y-2">
        {visibleQuestions.map((question) => (
          <Button
            key={question}
            type="button"
            variant="secondary"
            size="sm"
            className="h-auto w-full justify-start whitespace-normal rounded-md px-3 py-2 text-left text-xs leading-5"
            disabled={disabled}
            onClick={() => onQuestionClick(question)}
          >
            {question}
          </Button>
        ))}
      </div>
    </div>
  )
}
