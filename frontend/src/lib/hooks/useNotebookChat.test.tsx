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
  sendResearchMessage: vi.fn(),
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
    chatApiMock.sendResearchMessage.mockResolvedValue(createCompletedStream())
  })

  it('remembers the selected session independently for each chat tab', async () => {
    chatApiMock.listSessions.mockResolvedValue([
      {
        id: 'session:quick',
        title: 'Quick session',
        notebook_id: 'notebook:1',
        mode: 'quick',
        created: '2026-07-11T01:00:00Z',
        updated: '2026-07-11T01:00:00Z',
      },
      {
        id: 'session:research',
        title: 'Research session',
        notebook_id: 'notebook:1',
        mode: 'research',
        created: '2026-07-11T00:00:00Z',
        updated: '2026-07-11T00:00:00Z',
      },
    ])

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.currentSessionId).toBe('session:quick'))
    act(() => result.current.setChatMode('research'))
    await waitFor(() => expect(result.current.currentSessionId).toBe('session:research'))
    act(() => result.current.setChatMode('quick'))

    expect(result.current.currentSessionId).toBe('session:quick')
    expect(result.current.currentSessionIds).toEqual({
      quick: 'session:quick',
      research: 'session:research',
    })
  })

  it('starts a local blank conversation and creates it only on first send', async () => {
    chatApiMock.listSessions.mockResolvedValue([{
      id: 'session:existing',
      title: 'Existing',
      notebook_id: 'notebook:1',
      mode: 'quick',
      created: '2026-07-11T00:00:00Z',
      updated: '2026-07-11T00:00:00Z',
    }])
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:new',
      title: 'First question',
      notebook_id: 'notebook:1',
      mode: 'quick',
      created: '2026-07-11T01:00:00Z',
      updated: '2026-07-11T01:00:00Z',
    })

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.currentSessionId).toBe('session:existing'))
    act(() => result.current.startNewSession())
    expect(result.current.currentSessionId).toBeNull()
    expect(result.current.messages).toEqual([])
    expect(chatApiMock.createSession).not.toHaveBeenCalled()

    await act(async () => {
      await result.current.sendMessage('First question')
    })

    expect(chatApiMock.createSession).toHaveBeenCalledWith(expect.objectContaining({
      title: 'First question',
      mode: 'quick',
    }))
    expect(result.current.currentSessionId).toBe('session:new')
    expect(result.current.saveStatus).toBe('saved')
  })

  it('sends Research Agent turns without building the selected quick-chat context', async () => {
    chatApiMock.listSessions.mockResolvedValue([{
      id: 'session:research',
      title: 'Research session',
      notebook_id: 'notebook:1',
      mode: 'research',
      created: '2026-07-10T00:00:00Z',
      updated: '2026-07-10T00:00:00Z',
    }])
    chatApiMock.getSession.mockResolvedValue({
      id: 'session:research',
      title: 'Research session',
      notebook_id: 'notebook:1',
      mode: 'research',
      created: '2026-07-10T00:00:00Z',
      updated: '2026-07-10T00:00:00Z',
      messages: [],
    })

    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(chatApiMock.listSessions).toHaveBeenCalled())
    act(() => result.current.setChatMode('research'))
    await waitFor(() => expect(result.current.currentSessionId).toBe('session:research'))
    const contextCallsBeforeSend = chatApiMock.buildContext.mock.calls.length

    await act(async () => {
      await result.current.sendMessage('Compare the available evidence.')
    })

    expect(chatApiMock.buildContext).toHaveBeenCalledTimes(contextCallsBeforeSend)
    expect(chatApiMock.sendResearchMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        session_id: 'session:research',
        allow_cross_notebook_discovery: false,
      }),
      expect.any(AbortSignal),
    )
    expect(chatApiMock.sendMessage).not.toHaveBeenCalled()
  })

  it('passes cross-notebook discovery only after the user explicitly enables it', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:research-new',
      title: 'Find analogues',
      notebook_id: 'notebook:1',
      mode: 'research',
      created: '2026-07-10T00:00:00Z',
      updated: '2026-07-10T00:00:00Z',
    })
    const { result } = renderHook(
      () => useNotebookChat({
        notebookId: 'notebook:1',
        sources: [],
        notes: [],
        contextSelections: { sources: {}, notes: {} },
      }),
      { wrapper: createWrapper() },
    )

    act(() => {
      result.current.setChatMode('research')
      result.current.setAllowCrossNotebookDiscovery(true)
    })
    await act(async () => {
      await result.current.sendMessage('Find analogues in other notebooks.')
    })

    expect(chatApiMock.sendResearchMessage).toHaveBeenCalledWith(
      expect.objectContaining({ allow_cross_notebook_discovery: true }),
      expect.any(AbortSignal),
    )
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
    expect(result.current.activityMessageId).toMatch(/^temp-/)
    expect(result.current.activityTerminal).toBeNull()
    expect(result.current.activitySteps).toEqual([
      { stage: 'received', status: 'complete' },
      { stage: 'preparing_context', status: 'active' },
    ])

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

  it('turns structured SSE status events into a completed activity sequence', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'Trace the evidence',
      notebook_id: 'notebook:1',
      created: '2026-07-10T00:00:00Z',
      updated: '2026-07-10T00:00:00Z',
    })
    const payload = [
      'data: {"type":"chat_status","stage":"searching_notebook","status":"active"}\n\n',
      'data: {"type":"chat_status","stage":"searching_notebook","status":"complete"}\n\n',
      'data: {"type":"chat_status","stage":"reading_evidence","status":"active"}\n\n',
      'data: {"type":"ai_message","content":"Evidence summary"}\n\n',
      'data: {"type":"answer_complete"}\n\n',
    ].join('')
    chatApiMock.sendMessage.mockResolvedValue(new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(payload))
        controller.close()
      },
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

    await act(async () => {
      await result.current.sendMessage('Trace the evidence')
    })

    expect(result.current.activityTerminal).toBe('complete')
    expect(result.current.activitySteps).toEqual(expect.arrayContaining([
      { stage: 'received', status: 'complete' },
      { stage: 'context_ready', status: 'complete' },
      { stage: 'searching_notebook', status: 'complete' },
      { stage: 'reading_evidence', status: 'complete' },
      { stage: 'model_streaming', status: 'complete' },
    ]))
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

  it('surfaces heartbeat events as awaitingModel activity with elapsed seconds', async () => {
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'Heartbeat test',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })

    let release!: () => void
    const released = new Promise<void>((resolve) => { release = resolve })

    const heartbeatStream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"heartbeat","stage":"searching_notebook","elapsed_ms":5000}\n\n',
                ),
              }
            }
            if (step === 2) {
              // Pause until the test inspects the awaitingModel state, then deliver
              // the final completion frames.
              await released
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"ai_message","content":"hi"}\n\n' +
                  'data: {"type":"answer_complete"}\n\n' +
                  'data: {"type":"complete"}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>

    chatApiMock.sendMessage.mockResolvedValue(heartbeatStream)

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
      sendPromise = result.current.sendMessage('Hello?')
    })

    await waitFor(() => {
      expect(result.current.activityStatus).toBe('awaitingModel')
      expect(result.current.activityElapsedSeconds).toBeGreaterThan(0)
      expect(result.current.activityTotalElapsedSeconds).toBeGreaterThanOrEqual(5)
    })

    await act(async () => {
      release()
      await sendPromise!
    })

    expect(result.current.activityStatus).toBeNull()
    expect(result.current.activityElapsedSeconds).toBe(0)
    expect(result.current.activityTotalElapsedSeconds).toBeGreaterThanOrEqual(5)
  })

  it('renders llm_timeout as an inline AI bubble instead of a toast (scenario A: no prior AI chunks)', async () => {
    const { toast } = await import('@/lib/hooks/use-toast')
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'Timeout test',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })

    const timeoutStream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"error","error_code":"llm_timeout","timeout_seconds":3,"message":"Model response timed out after 3s. Try shrinking the included sources or notes and ask again."}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>

    chatApiMock.sendMessage.mockResolvedValue(timeoutStream)

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
      await result.current.sendMessage('Slow question')
    })

    // No toast, no console.error — the timeout is surfaced inline.
    expect(toast.error).not.toHaveBeenCalled()

    // Human optimistic bubble is preserved (refetch is mocked empty here).
    const humanMessages = result.current.messages.filter(m => m.type === 'human')
    expect(humanMessages.length).toBeGreaterThanOrEqual(1)

    // New AI bubble carries the warning prefix + localized body + diagnostic line.
    const aiMessages = result.current.messages.filter(m => m.type === 'ai')
    expect(aiMessages.length).toBe(1)
    const aiContent = aiMessages[0].content
    expect(aiContent).toContain('⚠️')
    expect(aiContent.toLowerCase()).toContain('timed out')
    expect(aiContent).toContain('error_code=llm_timeout')
    expect(aiContent).toContain('timeout_seconds=3')
    expect(aiContent).toContain('_Server message_')

    // Activity is reset; input box can accept a new question.
    expect(result.current.activityStatus).toBeNull()
    expect(result.current.activityElapsedSeconds).toBe(0)
    expect(result.current.isSending).toBe(false)
    expect(result.current.activityTerminal).toBe('error')
    expect(result.current.activitySteps.some(step => step.status === 'error')).toBe(true)
  })

  it('appends llm_timeout notice to the existing AI bubble when chunks already streamed (scenario B)', async () => {
    const { toast } = await import('@/lib/hooks/use-toast')
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: 'Mid-stream timeout test',
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })

    const midStreamTimeout = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"ai_message","content":"partial answer"}\n\n' +
                  'data: {"type":"error","error_code":"llm_timeout","timeout_seconds":3,"message":"Model response timed out after 3s."}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>

    chatApiMock.sendMessage.mockResolvedValue(midStreamTimeout)

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
      await result.current.sendMessage('Question that times out mid-stream')
    })

    expect(toast.error).not.toHaveBeenCalled()

    // Exactly one AI bubble — the timeout notice was appended, not a new bubble.
    const aiMessages = result.current.messages.filter(m => m.type === 'ai')
    expect(aiMessages.length).toBe(1)
    const aiContent = aiMessages[0].content
    expect(aiContent).toContain('partial answer')
    expect(aiContent).toContain('⚠️')
    expect(aiContent).toContain('error_code=llm_timeout')

    expect(result.current.activityStatus).toBeNull()
    expect(result.current.isSending).toBe(false)
  })

  it.each([
    {
      label: 'rate_limit',
      code: 'rate_limit',
      message: 'Rate limit exceeded. Please wait a moment and try again.',
      expectInBubbleLowercased: ['rate-limited'],
    },
    {
      label: 'authentication',
      code: 'authentication',
      message: 'Authentication failed. Please check your API key in Settings -> Credentials.',
      expectInBubbleLowercased: ['authentication failed'],
    },
    {
      label: 'network',
      code: 'network',
      message: 'Could not connect to the AI provider. Please check your network connection and provider URL.',
      expectInBubbleLowercased: ['could not reach the ai provider'],
    },
    {
      label: 'external_service',
      code: 'external_service',
      message: 'The AI provider is temporarily unavailable. Please try again in a few minutes.',
      expectInBubbleLowercased: ['ai provider returned an error'],
    },
    {
      label: 'unknown code falls back to generic template',
      code: 'something_weird',
      message: 'Specific upstream message',
      expectInBubbleLowercased: ['chat request did not complete'],
    },
  ])('renders SSE error_code=$label as inline AI bubble with localized guidance', async ({ code, message, expectInBubbleLowercased }) => {
    const { toast } = await import('@/lib/hooks/use-toast')
    chatApiMock.createSession.mockResolvedValue({
      id: 'session:1',
      title: `Error ${code} test`,
      notebook_id: 'notebook:1',
      created: '2026-06-12T00:00:00Z',
      updated: '2026-06-12T00:00:00Z',
    })

    const payload = JSON.stringify({ type: 'error', error_code: code, message })
    const errorStream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(`data: ${payload}\n\n`),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    chatApiMock.sendMessage.mockResolvedValue(errorStream)

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
      await result.current.sendMessage(`Trigger ${code}`)
    })

    expect(toast.error).not.toHaveBeenCalled()
    const aiMessages = result.current.messages.filter(m => m.type === 'ai')
    expect(aiMessages.length).toBe(1)
    const bubble = aiMessages[0].content
    expect(bubble).toContain('⚠️')
    expect(bubble).toContain(`error_code=${code}`)
    expect(bubble).toContain(`_Server message_: ${message}`)
    const lowered = bubble.toLowerCase()
    for (const snippet of expectInBubbleLowercased) {
      expect(lowered).toContain(snippet.toLowerCase())
    }

    expect(result.current.activityStatus).toBeNull()
    expect(result.current.activityElapsedSeconds).toBe(0)
    expect(result.current.isSending).toBe(false)
  })
})
