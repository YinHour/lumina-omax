'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { CheckCircle, Sparkles, Lightbulb, ChevronDown, Copy, Save } from 'lucide-react'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { convertReferencesToMarkdownLinks, createReferenceLinkComponent } from '@/lib/utils/source-references'
import { useModalManager } from '@/lib/hooks/use-modal-manager'
import { useTranslation } from '@/lib/hooks/use-translation'
import { toast } from '@/lib/hooks/use-toast'
import type { AskCoverage } from '@/lib/types/search'

interface StrategyData {
  reasoning: string
  searches: Array<{ term: string; instructions: string }>
}

interface StreamingResponseProps {
  isStreaming: boolean
  strategy: StrategyData | null
  answers: string[]
  finalAnswer: string | null
  coverage?: AskCoverage | null
  errorBubble?: string | null
  activityElapsedSeconds?: number
  onSaveRequest?: () => void
}

export function StreamingResponse({
  isStreaming,
  strategy,
  answers,
  finalAnswer,
  coverage,
  errorBubble,
  activityElapsedSeconds,
  onSaveRequest
}: StreamingResponseProps) {
  const [strategyOpen, setStrategyOpen] = useState(true)
  const [answersOpen, setAnswersOpen] = useState(true)
  const [copySuccess, setCopySuccess] = useState(false)
  const { openModal } = useModalManager()
  const { t } = useTranslation()

  const handleCopyToClipboard = async () => {
    if (!finalAnswer) return
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(finalAnswer)
        toast.success(t.common.copyToClipboard || 'Copied to clipboard')
        setCopySuccess(true)
        setTimeout(() => setCopySuccess(false), 2000)
      } else {
        const textArea = document.createElement('textarea')
        textArea.value = finalAnswer
        textArea.style.position = 'fixed'
        textArea.style.left = '-999999px'
        textArea.style.top = '-999999px'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        try {
          document.execCommand('copy')
          toast.success(t.common.copyToClipboard || 'Copied to clipboard')
          setCopySuccess(true)
          setTimeout(() => setCopySuccess(false), 2000)
        } catch {
          toast.error(t.common.error || 'Failed to copy')
        }
        document.body.removeChild(textArea)
      }
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
      toast.error(t.common.error || 'Failed to copy')
    }
  }

  const handleReferenceClick = (type: string, id: string) => {
    const modalType = type === 'source_insight' ? 'insight' : type as 'source' | 'note' | 'insight'

    try {
      openModal(modalType, id)
      // Note: The modal system uses URL parameters and doesn't throw errors for missing items.
      // The modal component itself will handle displaying "not found" states.
      // This try-catch is here for future enhancements or unexpected errors.
    } catch {
      const typeLabel = type === 'source_insight' ? 'insight' : type
      toast.error(t.common.itemNotFound.replace('{type}', typeLabel))
    }
  }

  if (!strategy && !answers.length && !finalAnswer && !isStreaming && !errorBubble) {
    return null
  }

  return (
    <div
      className="space-y-4 mt-6 min-w-0"
      role="region"
      aria-label={t.common.accessibility.askResponse}
      aria-live="polite"
      aria-busy={isStreaming}
    >
      {/* Strategy Section - Collapsible */}
      {strategy && (
        <Collapsible open={strategyOpen} onOpenChange={setStrategyOpen}>
          <Card>
            <CardHeader>
              <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-80">
                <CardTitle className="text-base flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  {t.common.strategy}
                </CardTitle>
                <ChevronDown className={`h-4 w-4 transition-transform ${strategyOpen ? 'rotate-180' : ''}`} />
              </CollapsibleTrigger>
            </CardHeader>
            <CollapsibleContent>
              <CardContent className="space-y-3 pt-0">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">{t.common.reasoning}:</p>
                  <p className="text-sm whitespace-pre-wrap">{strategy.reasoning}</p>
                </div>
                {strategy.searches.length > 0 && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">{t.common.searchTerms}:</p>
                    <div className="space-y-2">
                      {strategy.searches.map((search, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <Badge variant="outline" className="mt-0.5">{i + 1}</Badge>
                          <div className="flex-1">
                            <p className="text-sm font-medium">{search.term}</p>
                            <p className="text-xs text-muted-foreground">{search.instructions}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      )}

      {/* Individual Answers Section - Collapsible */}
      {answers.length > 0 && (
        <Collapsible open={answersOpen} onOpenChange={setAnswersOpen}>
          <Card>
            <CardHeader>
              <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-80">
                <CardTitle className="text-base flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-primary" />
                  {t.common.individualAnswers.replace('{count}', answers.length.toString())}
                </CardTitle>
                <ChevronDown className={`h-4 w-4 transition-transform ${answersOpen ? 'rotate-180' : ''}`} />
              </CollapsibleTrigger>
            </CardHeader>
            <CollapsibleContent>
              <CardContent className="space-y-2 pt-0">
                {answers.map((answer, i) => (
                  <div key={i} className="p-3 rounded-md bg-muted">
                    <MarkdownContent
                      content={answer}
                      onReferenceClick={handleReferenceClick}
                    />
                  </div>
                ))}
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      )}

      {coverage && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t.searchPage.coverageTitle}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-3">
              <CoverageMetric label={t.searchPage.totalSources} value={coverage.total_sources} />
              <CoverageMetric label={t.searchPage.embeddedSources} value={coverage.embedded_sources} />
              <CoverageMetric label={t.searchPage.retrievedSources} value={coverage.retrieved_sources} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Final Answer Section - Always Open */}
      {finalAnswer && (
        <Card className="border-primary">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-primary" />
              {t.common.finalAnswer}
            </CardTitle>
          </CardHeader>
          <CardContent className="min-w-0">
            <MarkdownContent
              content={finalAnswer}
              onReferenceClick={handleReferenceClick}
            />
            {/* Action buttons at the bottom of the final answer */}
            <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-border/50">
              <button
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={handleCopyToClipboard}
              >
                {copySuccess ? (
                  <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {t.common.copyToClipboard || 'Copy'}
              </button>
              {onSaveRequest && (
                <button
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  onClick={onSaveRequest}
                >
                  <Save className="h-3.5 w-3.5" />
                  {t.searchPage?.saveToNotebooks || t.common.saveToNote || 'Save to Notebooks'}
                </button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading Indicator */}
      {isStreaming && !finalAnswer && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <LoadingSpinner size="sm" />
          <span>
            {t.searchPage.processingQuestion}
            {typeof activityElapsedSeconds === 'number' && activityElapsedSeconds > 0
              ? `（${activityElapsedSeconds}s）`
              : ''}
          </span>
        </div>
      )}

      {/* Inline SSE error bubble (§32). Rendered after any partial answers
          so users see what was produced before the failure. */}
      {errorBubble && (
        <Card>
          <CardContent className="prose prose-sm dark:prose-invert max-w-none py-4">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
            >
              {errorBubble}
            </ReactMarkdown>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function CoverageMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
    </div>
  )
}

// Helper component to render ASK answers with markdown and clickable references.
function MarkdownContent({
  content,
  onReferenceClick
}: {
  content: string
  onReferenceClick: (type: string, id: string) => void
}) {
  // Convert references to markdown links
  const markdownWithLinks = convertReferencesToMarkdownLinks(content)

  // Create custom link component
  const LinkComponent = createReferenceLinkComponent(onReferenceClick)

  return (
    <div className="text-sm leading-7 break-words min-w-0 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          a: LinkComponent,
          p: ({ children }) => <p className="my-3 whitespace-pre-wrap">{children}</p>,
          h1: ({ children }) => <h1 className="mt-5 mb-3 text-xl font-semibold leading-tight">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-5 mb-3 text-lg font-semibold leading-tight">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-4 mb-2 text-base font-semibold leading-tight">{children}</h3>,
          ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-5">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-4 border-l-4 border-border pl-4 text-muted-foreground">
              {children}
            </blockquote>
          ),
          pre: ({ children }) => (
            <pre className="my-4 max-w-full overflow-x-auto rounded-md bg-muted p-3 text-xs leading-6">
              {children}
            </pre>
          ),
          code: ({ children, className }) => {
            const isBlock = className?.includes('language-')
            if (isBlock) {
              return <code className={className}>{children}</code>
            }
            return (
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {children}
              </code>
            )
          },
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
        {markdownWithLinks}
      </ReactMarkdown>
    </div>
  )
}
