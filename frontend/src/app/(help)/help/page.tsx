import { resolveDocPath, readDoc } from '@/lib/help/docs'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default async function HelpIndexPage() {
  const docPath = resolveDocPath(undefined)
  const content = docPath ? readDoc(docPath) : '# 帮助文档\n\n文档加载中...'

  const titleMatch = content.match(/^# (.+)$/m)
  const title = titleMatch ? titleMatch[1] : '帮助文档'
  const bodyWithoutTitle = content.replace(/^# .+\n\n?/, '')

  return (
    <article className="prose prose-sm prose-neutral dark:prose-invert max-w-none break-words
      prose-headings:font-semibold prose-a:text-blue-600 prose-a:break-all
      prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded
      prose-p:mb-4 prose-p:leading-7 prose-li:mb-2">
      <h1 className="text-2xl font-bold mb-6 pb-4 border-b">{title}</h1>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            const isExternal = href?.startsWith('http')
            return <a href={href} target={isExternal ? '_blank' : undefined} rel={isExternal ? 'noopener noreferrer' : undefined} {...props}>{children}</a>
          },
          h1: ({ children }) => <h1 className="mb-4 mt-6 text-2xl font-bold">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-3 mt-5 text-xl font-semibold">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-3 mt-4 text-lg font-semibold">{children}</h3>,
          h4: ({ children }) => <h4 className="mb-2 mt-4 text-base font-semibold">{children}</h4>,
          ul: ({ children }) => <ul className="mb-4 list-disc space-y-1 pl-6 [list-style-position:outside]">{children}</ul>,
          ol: ({ children }) => <ol className="mb-4 list-decimal space-y-1 pl-6 [list-style-position:outside] marker:text-foreground">{children}</ol>,
          li: ({ children }) => <li className="mb-1 pl-0.5">{children}</li>,
          blockquote: ({ children }) => <blockquote className="my-4 border-l-4 border-border pl-4 text-muted-foreground">{children}</blockquote>,
          pre: ({ children }) => <pre className="my-4 max-w-full overflow-x-auto rounded-md bg-muted p-3 text-xs leading-6">{children}</pre>,
          code: ({ children, className }) => {
            const isBlock = className?.includes('language-')
            if (isBlock) return <code className={className}>{children}</code>
            return <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{children}</code>
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
          img: ({ src, alt }) => (
            <span className="block text-sm text-muted-foreground italic">[图片: {alt || (typeof src === 'string' ? src : '')}]</span>
          ),
          hr: () => <hr className="my-6 border-border" />,
        }}
      >
        {bodyWithoutTitle}
      </ReactMarkdown>
    </article>
  )
}
