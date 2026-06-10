import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(process.cwd(), 'src/app/globals.css'), 'utf8')

describe('global design tokens', () => {
  it('defines warm semantic status and surface tokens', () => {
    expect(css).toContain('--color-highlight: var(--highlight);')
    expect(css).toContain(
      '--color-highlight-foreground: var(--highlight-foreground);'
    )
    expect(css).toContain('--color-success: var(--success);')
    expect(css).toContain('--color-warning: var(--warning);')
    expect(css).toContain('--shadow-surface:')
    expect(css).toContain('--motion-standard: 180ms;')
  })

  it('provides both warm light and dark theme values', () => {
    expect(css).toMatch(/:root\s*{[\s\S]*--background:\s*oklch\(/)
    expect(css).toMatch(/\.dark\s*{[\s\S]*--background:\s*oklch\(/)
    expect(css).toContain('--highlight:')
    expect(css).toContain('--sidebar-accent:')
  })

  it('removes legacy hover scaling', () => {
    expect(css).not.toContain('scale-[1.02]')
    expect(css).not.toContain('transform: translateY(-1px)')
  })

  it('respects reduced motion', () => {
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
  })
})
