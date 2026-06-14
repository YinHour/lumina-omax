import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { useNotebookChat } from './useNotebookChat'

const chatApiMock = vi.hoisted(() => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
  getSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn(),
  buildContext: vi.fn(),
  sendMessage: vi.fn(),
}))

vi.mock('@/lib/api/chat', () => ({
  chatApi: chatApiMock,
}))

vi.mock('@/lib/hooks/use-toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  return Wrapper
}

const createCompletedStream = () => {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('data: {"type":"complete"}\n\n'))
      controller.close()
    },
  })
}

const createSlowStream = () => {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      setTimeout(() => {
        controller.enqueue(new TextEncoder().encode('data: {"type":"complete"}\n\n'))
        controller.close()
      }, 25)
    },
  })
}

const createAnswerWithSuggestionsStream = () => {
  const payload = [
    'data: {"type":"ai_message","content":"The answer."}\n\n',
    'data: {"type":"suggested_questions","questions":["Q1?","Q2?","Q3?"]}\n\n',
    'data: {"type":"complete"}\n\n',
  ].join('')
  const encoded = new TextEncoder().encode(payload)

  return {
    getReader: () => {
      let readCount = 0
      return {
        read: vi.fn(async () => {
          readCount += 1
          if (readCount === 1) {
            return { done: false, value: encoded }
          }
          return { done: true, value: undefined }
        }),
      }
    },
  } as unknown as ReadableStream<Uint8Array>
}

const createAnswerWithCustomSuggestionsStream = (
  answer: string,
  questions: string[],
) => {
  const payload = [
    `data: ${JSON.stringify({ type: 'ai_message', content: answer })}\n\n`,
    `data: ${JSON.stringify({ type: 'suggested_questions', questions })}\n\n`,
    'data: {"type":"complete"}\n\n',
  ].join('')
  const encoded = new TextEncoder().encode(payload)

  return {
    getReader: () => {
      let readCount = 0
      return {
        read: vi.fn(async () => {
          readCount += 1
          if (readCount === 1) {
            return { done: false, value: encoded }
          }
          return { done: true, value: undefined }
        }),
      }
    },
  } as unknown as ReadableStream<Uint8Array>
}

const createDelayedSuggestionsStream = () => {
  let releaseSuggestions!: () => void
  const suggestionsReady = new Promise<void>((resolve) => {
    releaseSuggestions = resolve
  })

  const stream = {
    getReader: () => {
      let readCount = 0
      return {
        read: vi.fn(async () => {
          readCount += 1
          if (readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"ai_message","content":"The answer."}\n\n' +
                'data: {"type":"answer_complete"}\n\n',
              ),
            }
          }
          if (readCount === 2) {
            await suggestionsReady
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"suggested_questions","questions":["Q1?","Q2?","Q3?"]}\n\n' +
                'data: {"type":"complete"}\n\n',
              ),
            }
          }
          return { done: true, value: undefined }
        }),
      }
    },
  } as unknown as ReadableStream<Uint8Array>

  return { stream, releaseSuggestions }
}

describe('useNotebookChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    chatApiMock.listSessions.mockResolvedValue([])
    chatApiMock.getSession.mockResolvedValue({
      id: 'session:1',
      title: 'Session',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
      messages: [],
    })
    chatApiMock.buildContext.mockResolvedValue({
      context: { sources: [], notes: [] },
      token_count: 0,
      char_count: 0,
    })
    chatApiMock.sendMessage.mockResolvedValue(createCompletedStream())
  })

  it('guards against duplicate sends while creating the first session', async () => {
    let resolveSession: (session: {
      id: string
      title: string
      notebook_id: string
      created: string
      updated: string
    }) => void
    const sessionPromise = new Promise<{
      id: string
      title: string
      notebook_id: string
      created: string
      updated: string
    }>((resolve) => {
      resolveSession = resolve
    })
    chatApiMock.createSession.mockReturnValue(sessionPromise)

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    let firstSend: Promise<void>
    let secondSend: Promise<void>
    await act(async () => {
      firstSend = result.current.sendMessage('What should I inspect next?')
      secondSend = result.current.sendMessage('What should I inspect next?')
    })

    expect(chatApiMock.createSession).toHaveBeenCalledTimes(1)

    resolveSession!({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })

    await act(async () => {
      await Promise.all([firstSend!, secondSend!])
    })

    expect(chatApiMock.sendMessage).toHaveBeenCalledTimes(1)
  })

  it('shows the user message and context activity before the first session is created', async () => {
    let resolveSession: (session: {
      id: string
      title: string
      notebook_id: string
      created: string
      updated: string
    }) => void
    chatApiMock.createSession.mockReturnValue(new Promise((resolve) => {
      resolveSession = resolve
    }))

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    let sendPromise: Promise<void>
    await act(async () => {
      sendPromise = result.current.sendMessage('What should I inspect next?')
    })

    expect(result.current.messages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: 'human',
          content: 'What should I inspect next?',
        }),
      ]),
    )
    expect(result.current.activityStatus).toBe('gettingContext')

    resolveSession!({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })

    await act(async () => {
      await sendPromise!
    })
  })

  it('keeps the optimistic user message when the new empty session refetches while sending', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })
    chatApiMock.sendMessage.mockResolvedValue(createSlowStream())

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    let sendPromise: Promise<void>
    await act(async () => {
      sendPromise = result.current.sendMessage('What should I inspect next?')
    })

    await waitFor(() => expect(result.current.currentSessionId).toBe('session:1'))

    await act(async () => {
      await chatApiMock.getSession.mock.results[0]?.value
    })

    expect(result.current.messages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: 'human',
          content: 'What should I inspect next?',
        }),
      ]),
    )

    await act(async () => {
      await sendPromise!
    })
  })

  it('keeps suggested questions after persisted session messages replace streamed message ids', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })
    chatApiMock.getSession.mockResolvedValue({
      id: 'session:1',
      title: 'Session',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
      messages: [
        {
          id: 'persisted-human-1',
          type: 'human',
          content: 'What should I inspect next?',
          timestamp: '2026-06-12T00:00:01Z',
        },
        {
          id: 'persisted-ai-1',
          type: 'ai',
          content: 'The answer.',
          timestamp: '2026-06-12T00:00:02Z',
        },
      ],
    })
    chatApiMock.sendMessage.mockResolvedValue(createAnswerWithSuggestionsStream())

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      await result.current.sendMessage('What should I inspect next?')
    })

    await waitFor(() => {
      expect(result.current.suggestedQuestionsByMessageId['persisted-ai-1']).toEqual(['Q1?', 'Q2?', 'Q3?'])
    })
  })

  it('marks sending complete after answer_complete while continuing to read suggestions', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })
    chatApiMock.getSession.mockResolvedValue({
      id: 'session:1',
      title: 'Session',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
      messages: [
        {
          id: 'persisted-human-1',
          type: 'human',
          content: 'What should I inspect next?',
          timestamp: '2026-06-12T00:00:01Z',
        },
        {
          id: 'persisted-ai-1',
          type: 'ai',
          content: 'The answer.',
          timestamp: '2026-06-12T00:00:02Z',
        },
      ],
    })
    const delayedStream = createDelayedSuggestionsStream()
    chatApiMock.sendMessage.mockResolvedValue(delayedStream.stream)

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      void result.current.sendMessage('What should I inspect next?')
    })

    await waitFor(() => {
      expect(result.current.isSending).toBe(false)
    })

    delayedStream.releaseSuggestions()

    await waitFor(() => {
      expect(result.current.suggestedQuestionsByMessageId['persisted-ai-1']).toEqual(['Q1?', 'Q2?', 'Q3?'])
    })
  })

  it('attaches fresh suggested questions to each completed answer', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })
    let persistedSession = {
      id: 'session:1',
      title: 'Session',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
      messages: [] as Array<{
        id: string
        type: 'human' | 'ai'
        content: string
        timestamp: string
      }>,
    }
    chatApiMock.getSession.mockImplementation(async () => persistedSession)
    const firstPersistedMessages = [
      {
        id: 'persisted-human-1',
        type: 'human' as const,
        content: 'What should I inspect first?',
        timestamp: '2026-06-12T00:00:01Z',
      },
      {
        id: 'persisted-ai-1',
        type: 'ai' as const,
        content: 'First answer.',
        timestamp: '2026-06-12T00:00:02Z',
      },
    ]
    const secondPersistedMessages = [
      {
        id: 'persisted-human-1',
        type: 'human' as const,
        content: 'What should I inspect first?',
        timestamp: '2026-06-12T00:00:01Z',
      },
      {
        id: 'persisted-ai-1',
        type: 'ai' as const,
        content: 'First answer.',
        timestamp: '2026-06-12T00:00:02Z',
      },
      {
        id: 'persisted-human-2',
        type: 'human' as const,
        content: 'What should I inspect second?',
        timestamp: '2026-06-12T00:00:03Z',
      },
      {
        id: 'persisted-ai-2',
        type: 'ai' as const,
        content: 'Second answer.',
        timestamp: '2026-06-12T00:00:04Z',
      },
    ]
    chatApiMock.sendMessage
      .mockResolvedValueOnce(
        createAnswerWithCustomSuggestionsStream('First answer.', [
          'First Q1?',
          'First Q2?',
          'First Q3?',
        ]),
      )
      .mockResolvedValueOnce(
        createAnswerWithCustomSuggestionsStream('Second answer.', [
          'Second Q1?',
          'Second Q2?',
          'Second Q3?',
        ]),
      )

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      persistedSession = { ...persistedSession, messages: firstPersistedMessages }
      await result.current.sendMessage('What should I inspect first?')
    })

    await act(async () => {
      persistedSession = { ...persistedSession, messages: secondPersistedMessages }
      await result.current.sendMessage('What should I inspect second?')
    })

    await waitFor(() => {
      expect(
        result.current.suggestedQuestionsByMessageId['persisted-ai-1'],
      ).toEqual(['First Q1?', 'First Q2?', 'First Q3?'])
      expect(
        result.current.suggestedQuestionsByMessageId['persisted-ai-2'],
      ).toEqual(['Second Q1?', 'Second Q2?', 'Second Q3?'])
    })
  })

  it('builds chat context from the currently selected sources only', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [
          {
            id: 'source:selected',
            title: 'Selected source',
            status: 'completed',
            updated: '2026-06-12T00:00:00Z',
          } as never,
          {
            id: 'source:filtered-out',
            title: 'Filtered out source',
            status: 'completed',
            updated: '2026-06-12T00:00:00Z',
          } as never,
        ],
        notes: [],
        contextSelections: {
          sources: {
            'source:selected': 'full',
            'source:filtered-out': 'off',
          },
          notes: {},
        },
      }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      await result.current.sendMessage('What should I inspect next?')
    })

    expect(chatApiMock.buildContext).toHaveBeenCalledWith({
      notebook_id: 'notebook:1',
      context_config: {
        sources: {
          'source:selected': 'full content',
          'source:filtered-out': 'not in',
        },
        notes: {},
      },
    })
  })

  it('reuses the latest built context when sending without selection changes', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'What should I inspect next?',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })
    chatApiMock.buildContext.mockResolvedValue({
      context: { sources: [{ id: 'source:1', full_text: 'cached context' }], notes: [] },
      token_count: 12,
      char_count: 64,
    })

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [
          {
            id: 'source:1',
            title: 'Source',
            status: 'completed',
            updated: '2026-06-12T00:00:00Z',
          } as never,
        ],
        notes: [],
        contextSelections: { sources: { 'source:1': 'full' }, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => {
      expect(result.current.tokenCount).toBe(12)
    })

    await act(async () => {
      await result.current.sendMessage('What should I inspect next?')
    })

    expect(chatApiMock.buildContext).toHaveBeenCalledTimes(1)
    expect(chatApiMock.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        context: { sources: [{ id: 'source:1', full_text: 'cached context' }], notes: [] },
      }),
      expect.any(AbortSignal),
    )
  })
})
