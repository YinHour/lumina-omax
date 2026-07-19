import { beforeEach, describe, expect, it, vi } from 'vitest'
import { chatApi } from './chat'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
}))

vi.mock('./client', () => ({
  default: apiClientMock,
}))

describe('chatApi transcript pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads Research Skill metadata through the relative API client', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      data: [{ id: 'doe-statistical-plan', version: '1.0.0' }],
    })

    const skills = await chatApi.listResearchSkills()

    expect(skills).toEqual([
      { id: 'doe-statistical-plan', version: '1.0.0' },
    ])
    expect(apiClientMock.get).toHaveBeenCalledWith('/chat/research/skills')
  })

  it('fetches and orders every transcript page for Markdown export', async () => {
    apiClientMock.get
      .mockResolvedValueOnce({
        data: {
          messages: [
            { id: 'm3', type: 'human', content: 'third', sequence: 3 },
            { id: 'm4', type: 'ai', content: 'fourth', sequence: 4 },
          ],
          has_more: true,
          next_cursor: 3,
        },
      })
      .mockResolvedValueOnce({
        data: {
          messages: [
            { id: 'm1', type: 'human', content: 'first', sequence: 1 },
            { id: 'm2', type: 'ai', content: 'second', sequence: 2 },
          ],
          has_more: false,
          next_cursor: null,
        },
      })

    const messages = await chatApi.getAllSessionMessages('chat_session:1')

    expect(messages.map(message => message.id)).toEqual(['m1', 'm2', 'm3', 'm4'])
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/chat/sessions/chat_session:1',
      { params: { limit: 200 } },
    )
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/chat/sessions/chat_session:1',
      { params: { limit: 200, before_sequence: 3 } },
    )
  })
})
