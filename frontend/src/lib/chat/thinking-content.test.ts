import { describe, expect, it } from 'vitest'

import { stripThinkingContent } from './thinking-content'

describe('stripThinkingContent', () => {
  it('removes complete thinking blocks', () => {
    expect(
      stripThinkingContent('<think>private reasoning</think>Public answer'),
    ).toBe('Public answer')
  })

  it('hides an unfinished thinking block while streaming', () => {
    expect(stripThinkingContent('<think>private reasoning')).toBe('')
    expect(stripThinkingContent('Prefix\n<think>private reasoning')).toBe('Prefix')
  })

  it('handles a missing opening tag from reasoning models', () => {
    expect(stripThinkingContent('private reasoning</think>Public answer')).toBe(
      'Public answer',
    )
  })

  it('preserves ordinary markdown and raw HTML', () => {
    const content = '## Result\n\n<table><tbody><tr><td>42</td></tr></tbody></table>'
    expect(stripThinkingContent(content)).toBe(content)
  })
})
