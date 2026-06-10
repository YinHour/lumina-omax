import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(process.cwd(), 'src/app/globals.css'), 'utf8')

function extractFlatBlock(source: string, selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(
    new RegExp(`(?:^|\\n)${escapedSelector}\\s*\\{([^{}]*)\\}`)
  )

  expect(match, `Expected a flat ${selector} block`).not.toBeNull()
  return match![1]
}

describe('global design tokens', () => {
  it('defines warm semantic status and surface tokens', () => {
    const theme = extractFlatBlock(css, '@theme inline')

    expect(theme).toContain('--color-highlight: var(--highlight);')
    expect(theme).toContain(
      '--color-highlight-foreground: var(--highlight-foreground);'
    )
    expect(theme).toContain('--color-success: var(--success);')
    expect(theme).toContain(
      '--color-success-foreground: var(--success-foreground);'
    )
    expect(theme).toContain('--color-warning: var(--warning);')
    expect(theme).toContain(
      '--color-warning-foreground: var(--warning-foreground);'
    )
    expect(css).toContain('--shadow-surface:')
    expect(css).toContain('--motion-standard: 180ms;')
  })

  it('provides both warm light and dark theme values', () => {
    const lightTheme = extractFlatBlock(css, ':root')
    const darkTheme = extractFlatBlock(css, '.dark')
    const colorVariables = [
      'background',
      'highlight',
      'highlight-foreground',
      'success',
      'success-foreground',
      'warning',
      'warning-foreground',
    ]

    for (const theme of [lightTheme, darkTheme]) {
      for (const variable of colorVariables) {
        expect(theme).toMatch(
          new RegExp(`--${variable}:\\s*oklch\\([^;]+\\);`)
        )
      }
    }
  })

  it('removes legacy hover scaling', () => {
    expect(css).not.toContain('scale-[1.02]')
    expect(css).not.toContain('transform: translateY(-1px)')
  })

  it('respects reduced motion', () => {
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
  })
})
