import { SourceChatMessage } from '@/lib/types/api'
import { stripThinkingContent } from '@/lib/chat/thinking-content'

interface BuildChatMarkdownOptions {
  title: string
  messages: SourceChatMessage[]
  exportedAt: Date
  userLabel: string
  assistantLabel: string
}

export function buildChatMarkdown({
  title,
  messages,
  exportedAt,
  userLabel,
  assistantLabel,
}: BuildChatMarkdownOptions): string {
  const sections = messages.map(message => {
    const label = message.type === 'human' ? userLabel : assistantLabel
    const content = message.type === 'ai'
      ? stripThinkingContent(message.content)
      : message.content
    return `## ${label}\n\n${content.trim()}`
  })

  return [
    `# ${title}`,
    `> Exported: ${exportedAt.toISOString()}`,
    ...sections,
    '',
  ].join('\n\n')
}

export function downloadChatMarkdown(filename: string, markdown: string): void {
  const safeName = filename
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, ' ')
    .slice(0, 80) || 'conversation'
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${safeName}.md`
  anchor.click()
  URL.revokeObjectURL(url)
}
