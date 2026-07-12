import { describe, expect, it } from 'vitest'
import { buildChatMarkdown } from './export-chat-markdown'

describe('buildChatMarkdown', () => {
  it('exports visible human and assistant content without thinking blocks', () => {
    const markdown = buildChatMarkdown({
      title: 'Catalyst review',
      exportedAt: new Date('2026-07-11T00:00:00.000Z'),
      userLabel: 'User',
      assistantLabel: 'Assistant',
      messages: [
        { id: 'h1', type: 'human', content: 'Compare the evidence.' },
        { id: 'a1', type: 'ai', content: '<think>private reasoning</think>Public conclusion.' },
      ],
    })

    expect(markdown).toContain('# Catalyst review')
    expect(markdown).toContain('## User\n\nCompare the evidence.')
    expect(markdown).toContain('## Assistant\n\nPublic conclusion.')
    expect(markdown).not.toContain('private reasoning')
    expect(markdown).toContain('2026-07-11T00:00:00.000Z')
  })
})
