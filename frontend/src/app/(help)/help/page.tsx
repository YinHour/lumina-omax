import { resolveDocPath, readDoc } from '@/lib/help/docs'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default async function HelpIndexPage() {
  const docPath = resolveDocPath(undefined)
  const content = docPath ? readDoc(docPath) : '# 帮助文档\n\n文档加载中...'

  // Extract title
  const titleMatch = content.match(/^# (.+)$/m)
  const title = titleMatch ? titleMatch[1] : '帮助文档'
  const bodyWithoutTitle = content.replace(/^# .+\n\n?/, '')

  return (
    <article className="prose prose-slate dark:prose-invert max-w-none prose-headings:scroll-mt-20 prose-a:text-teal-400 prose-code:text-sm">
      <h1 className="text-2xl font-bold mb-6 pb-4 border-b">{title}</h1>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            const isExternal = href?.startsWith('http')
            return (
              <a
                href={href}
                target={isExternal ? '_blank' : undefined}
                rel={isExternal ? 'noopener noreferrer' : undefined}
                {...props}
              >
                {children}
              </a>
            )
          },
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full">{children}</table>
            </div>
          ),
          pre: ({ children }) => (
            <pre className="bg-muted rounded-lg p-4 overflow-x-auto text-sm">{children}</pre>
          ),
          code: ({ children, className }) => {
            const isInline = !className
            return isInline ? (
              <code className="bg-muted px-1.5 py-0.5 rounded text-sm">{children}</code>
            ) : (
              <code className={className}>{children}</code>
            )
          },
        }}
      >
        {bodyWithoutTitle}
      </ReactMarkdown>
    </article>
  )
}
