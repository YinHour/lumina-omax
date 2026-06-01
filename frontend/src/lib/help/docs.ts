import fs from 'fs'
import path from 'path'

const DOCS_ROOT = path.resolve(process.cwd(), '..', 'docs')

export interface HelpNavItem {
  label: string
  href: string
  children?: HelpNavItem[]
}

/** Parse section prefix like "3-USER-GUIDE" → "User Guide" */
function parseLabel(name: string): string {
  return name.replace(/^\d+-/, '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/** Build navigation tree from docs/ directory */
export function getHelpNav(): HelpNavItem[] {
  const entries = fs.readdirSync(DOCS_ROOT, { withFileTypes: true })
    .filter(e => e.isDirectory() && /^\d+-/.test(e.name))
    .sort((a, b) => a.name.localeCompare(b.name))

  return entries.map(dir => {
    const dirPath = path.join(DOCS_ROOT, dir.name)
    const files = fs.readdirSync(dirPath, { withFileTypes: true })
      .filter(e => e.isFile() && e.name.endsWith('.md') && e.name !== 'index.md')
      .sort((a, b) => a.name.localeCompare(b.name))

    const children: HelpNavItem[] = files.map(f => {
      const slug = f.name.replace(/\.md$/, '')
      return {
        label: parseLabel(slug),
        href: `/help/${dir.name}/${slug}`,
      }
    })

    return {
      label: parseLabel(dir.name),
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

  // If only section name (e.g., /help/3-USER-GUIDE), return index.md
  if (slugs.length === 1) {
    const indexPath = path.join(dirPath, 'index.md')
    if (fs.existsSync(indexPath)) return indexPath
    return null
  }

  // Specific doc (e.g., /help/3-USER-GUIDE/adding-sources)
  const docPath = path.join(dirPath, `${slugs[1]}.md`)
  if (fs.existsSync(docPath)) return docPath
  return null
}

/** Read markdown content from a doc path */
export function readDoc(filePath: string): string {
  return fs.readFileSync(filePath, 'utf-8')
}

/** Get section name from slug (for active state detection) */
export function getSectionFromSlug(slugs: string[] | undefined): string | null {
  if (!slugs || slugs.length === 0) return null
  return slugs[0]
}
