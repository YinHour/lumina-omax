import fs from 'fs'
import path from 'path'

const DOCS_ROOT = path.resolve(process.cwd(), '..', 'docs', 'user_docs')

export interface HelpNavItem {
  label: string
  href: string
  children?: HelpNavItem[]
}

/** Chapters to include in help (exclude dev-only sections) */
const INCLUDED_CHAPTERS = new Set([
  '2-CORE-CONCEPTS',
  '3-USER-GUIDE',
  '5-CONFIGURATION',
  '6-TROUBLESHOOTING',
])

/** Chinese section labels */
const SECTION_LABELS: Record<string, string> = {
  '2-CORE-CONCEPTS': '核心概念',
  '3-USER-GUIDE': '用户指南',
  '5-CONFIGURATION': '配置指南',
  '6-TROUBLESHOOTING': '故障排查',
}

/** Chinese labels for individual doc files */
const DOC_LABELS: Record<string, string> = {
  'notebooks-sources-notes': '笔记本·来源·笔记',
  'ai-context-rag': 'AI 上下文与 RAG',
  'chat-vs-transformations': '聊天 vs 转换',
  'interface-overview': '界面总览',
  'adding-sources': '添加来源',
  'working-with-notes': '笔记管理',
  'chat-effectively': '高效聊天',
  'creating-podcasts': '创建播客',
  'search': '搜索指南',
  'transformations': '内容转换',
  'citations': '引用与验证',
  'api-configuration': 'API 配置',
  'index': '概览',
  'ai-providers': 'AI 提供商配置',
  'security': '安全配置',
  'environment-reference': '环境变量参考',
  'database': '数据库配置',
  'reverse-proxy': '反向代理',
  'ollama': 'Ollama 指南',
  'openai-compatible': 'OpenAI 兼容端点',
  'local-tts': '本地 TTS（文本转语音）',
  'local-stt': '本地 STT（语音转文本）',
  'mcp-integration': 'MCP 集成',
  'advanced': '高级调优',
  'quick-fixes': '快速修复',
  'ai-chat-issues': 'AI 与聊天问题',
  'connection-issues': '连接问题',
  'faq': '常见问题',
}

function getLabel(dirName: string, fileName?: string): string {
  if (fileName) {
    const key = fileName.replace(/\.md$/, '')
    if (DOC_LABELS[key]) return DOC_LABELS[key]
    return key.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }
  if (SECTION_LABELS[dirName]) return SECTION_LABELS[dirName]
  return dirName.replace(/^\d+-/, '').replace(/-/g, ' ')
}

/** Build navigation tree from docs/ directory */
export function getHelpNav(): HelpNavItem[] {
  const entries = fs.readdirSync(DOCS_ROOT, { withFileTypes: true })
    .filter(e => e.isDirectory() && INCLUDED_CHAPTERS.has(e.name))
    .sort((a, b) => a.name.localeCompare(b.name))

  return entries.map(dir => {
    const dirPath = path.join(DOCS_ROOT, dir.name)
    const files = fs.readdirSync(dirPath, { withFileTypes: true })
      .filter(e => e.isFile() && e.name.endsWith('.md') && e.name !== 'index.md')
      .sort((a, b) => a.name.localeCompare(b.name))

    const children: HelpNavItem[] = files.map(f => {
      const slug = f.name.replace(/\.md$/, '')
      return {
        label: getLabel(dir.name, f.name),
        href: `/help/${dir.name}/${slug}`,
      }
    })

    return {
      label: getLabel(dir.name),
      href: `/help/${dir.name}`,
      children: children.length > 0 ? children : undefined,
    }
  })
}

/** Resolve a help URL slug to a file path, returning null if not found */
export function resolveDocPath(slugs: string[] | undefined): string | null {
  if (!slugs || slugs.length === 0) {
    const indexPath = path.join(DOCS_ROOT, 'index.md')
    if (fs.existsSync(indexPath)) return indexPath
    return null
  }

  const dirPath = path.join(DOCS_ROOT, slugs[0])
  if (!fs.existsSync(dirPath)) return null

  if (slugs.length === 1) {
    const indexPath = path.join(dirPath, 'index.md')
    if (fs.existsSync(indexPath)) return indexPath
    return null
  }

  const docPath = path.join(dirPath, `${slugs[1]}.md`)
  if (fs.existsSync(docPath)) return docPath
  return null
}

/** Read markdown content from a doc path */
export function readDoc(filePath: string): string {
  return fs.readFileSync(filePath, 'utf-8')
}
