import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(process.cwd(), 'src/app/globals.css'), 'utf8')
const representativePages = [
  'src/app/(dashboard)/notebooks/page.tsx',
  'src/app/(dashboard)/transformations/page.tsx',
  'src/app/(dashboard)/settings/page.tsx',
  'src/app/(dashboard)/advanced/page.tsx',
  'src/app/(dashboard)/search/page.tsx',
]
const rootLayout = 'src/app/layout.tsx'
const interactiveComponents = [
  'src/components/common/ThemeToggle.tsx',
  'src/components/common/LanguageToggle.tsx',
  'src/app/(dashboard)/notebooks/components/NotebookCard.tsx',
  'src/components/sources/SourceCard.tsx',
]
const legacyScaleClass = `scale-${'[1.02]'}`
const legacyTranslateRule = `transform: translate${'Y'}(-1px)`
const legacyHelperClasses = ['sidebar-menu' + '-item', 'card' + '-hover']
type Color = [number, number, number]

function extractFlatBlock(source: string, selector: string) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(
    new RegExp(`(?:^|\\n)${escapedSelector}\\s*\\{([^{}]*)\\}`)
  )

  expect(match, `Expected a flat ${selector} block`).not.toBeNull()
  return match![1]
}

function parseOklchVariable(block: string, variable: string): Color {
  const match = block.match(
    new RegExp(
      `--${variable}:\\s*oklch\\(\\s*([\\d.]+)\\s+([\\d.]+)\\s+([\\d.]+)\\s*\\);`
    )
  )

  expect(match, `Expected --${variable} to use a numeric OKLCH value`).not.toBeNull()
  return match!.slice(1).map(Number) as Color
}

function oklchToSrgb([lightness, chroma, hue]: Color): Color {
  const angle = (hue * Math.PI) / 180
  const a = chroma * Math.cos(angle)
  const b = chroma * Math.sin(angle)
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3
  const linearRgb: Color = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ]

  return linearRgb.map((channel) => {
    const encoded =
      channel <= 0.0031308
        ? 12.92 * channel
        : 1.055 * channel ** (1 / 2.4) - 0.055
    return Math.min(1, Math.max(0, encoded))
  }) as Color
}

function composite(foreground: Color, background: Color, alpha: number): Color {
  return foreground.map(
    (channel, index) => channel * alpha + background[index] * (1 - alpha)
  ) as Color
}

function relativeLuminance(color: Color) {
  const [red, green, blue] = color.map((channel) =>
    channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4
  )
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

function contrastRatio(first: Color, second: Color) {
  const luminances = [relativeLuminance(first), relativeLuminance(second)].sort(
    (a, b) => b - a
  )
  return (luminances[0] + 0.05) / (luminances[1] + 0.05)
}

describe('global design tokens', () => {
  it('uses shared page layout primitives on representative pages', () => {
    for (const page of representativePages) {
      const source = readFileSync(join(process.cwd(), page), 'utf8')
      expect(source, page).toContain('PageContainer')
      expect(source, page).toContain('PageHeader')
    }
  })

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

  it('keeps app typography independent from build-time network access', () => {
    const layout = readFileSync(join(process.cwd(), rootLayout), 'utf8')

    expect(layout).not.toContain('next/font/google')
    expect(layout).toContain('font-sans')
    expect(css).toContain('--font-sans: Inter, ui-sans-serif, system-ui')
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

  it('keeps light success treatments at WCAG AA contrast', () => {
    const lightTheme = extractFlatBlock(css, ':root')
    const success = oklchToSrgb(parseOklchVariable(lightTheme, 'success'))
    const successForeground = oklchToSrgb(
      parseOklchVariable(lightTheme, 'success-foreground')
    )
    const backgrounds = ['background', 'card'].map((variable) => [
      variable,
      oklchToSrgb(parseOklchVariable(lightTheme, variable)),
    ]) as [string, Color][]
    const ratios = [
      ['filled success', contrastRatio(success, successForeground), 4.5],
      ...backgrounds.flatMap(([name, background]) => [
        [`success text on ${name}`, contrastRatio(success, background), 4.5],
        [
          `success text on 14% success over ${name}`,
          contrastRatio(success, composite(success, background, 0.14)),
          4.5,
        ],
        [
          `success text on 20% success over ${name}`,
          contrastRatio(success, composite(success, background, 0.2)),
          4.7,
        ],
      ]),
    ] as [string, number, number][]

    for (const [use, ratio, minimum] of ratios) {
      expect(ratio, use).toBeGreaterThanOrEqual(minimum)
    }
  })

  it('removes legacy hover scaling', () => {
    expect(css).not.toContain(legacyScaleClass)
    expect(css).not.toContain(legacyTranslateRule)
  })

  it('keeps interactive components off legacy helper classes', () => {
    for (const component of interactiveComponents) {
      const source = readFileSync(join(process.cwd(), component), 'utf8')

      for (const legacyClass of legacyHelperClasses) {
        expect(source, component).not.toContain(legacyClass)
      }
    }
  })

  it('respects reduced motion', () => {
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
  })
})
