import { describe, expect, it } from 'vitest'
import { normalizeMathMarkdown } from './normalize-math'

describe('normalizeMathMarkdown', () => {
  it('moves model-produced single-line double-dollar formulas into display blocks', () => {
    expect(normalizeMathMarkdown('Before $$x = 1$$ after')).toBe(
      'Before \n\n$$\nx = 1\n$$\n\n after'
    )
  })

  it('does not rewrite formulas shown as code', () => {
    const content = '`$$x = 1$$`\n\n```text\n$$y = 2$$\n```'
    expect(normalizeMathMarkdown(content)).toBe(content)
  })

  it('keeps already well-formed multiline display math unchanged', () => {
    const content = '$$\nx = 1\n$$'
    expect(normalizeMathMarkdown(content)).toBe(content)
  })

  it('treats the rest of a line after an unmatched backtick as code', () => {
    const content = 'Before `unclosed $$x = 1$$'
    expect(normalizeMathMarkdown(content)).toBe(content)
  })
})
