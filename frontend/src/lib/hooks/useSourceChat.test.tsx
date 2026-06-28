import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { useSourceChat } from './useSourceChat'

const sourceChatApiMock = vi.hoisted(() => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
  getSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn(),
  sendMessage: vi.fn(),
}))

vi.mock('@/lib/api/source-chat', () => ({
  sourceChatApi: sourceChatApiMock,
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

const createSession = () => ({
  id: 'session:1',
  title: 'Source chat',
  source_id: 'source:1',
  created: '2026-06-28T00:00:00Z',
  updated: '2026-06-28T00:00:00Z',
})

describe('useSourceChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sourceChatApiMock.listSessions.mockResolvedValue([createSession()])
    sourceChatApiMock.getSession.mockResolvedValue({
      ...createSession(),
      messages: [],
    })
  })

  it('renders SSE llm_timeout as an inline AI bubble (scenario A: no prior chunks)', async () => {
    const { toast } = await import('@/lib/hooks/use-toast')

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
                  'data: {"type":"error","error_code":"llm_timeout","timeout_seconds":3,"message":"Model response timed out after 3s."}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    sourceChatApiMock.sendMessage.mockResolvedValue(timeoutStream)

    const { result } = renderHook(() => useSourceChat('source:1'), {
      wrapper: createWrapper(),
    })

    // Wait for the session to be auto-selected.
    await waitFor(() => expect(result.current.currentSessionId).toBe('session:1'))

    await act(async () => {
      await result.current.sendMessage('Slow question')
    })

    expect(toast.error).not.toHaveBeenCalled()
    const aiMessages = result.current.messages.filter((m) => m.type === 'ai')
    expect(aiMessages.length).toBe(1)
    const bubble = aiMessages[0].content
    expect(bubble).toContain('⚠️')
    expect(bubble.toLowerCase()).toContain('timed out')
    expect(bubble).toContain('error_code=llm_timeout')
    expect(bubble).toContain('timeout_seconds=3')

    expect(result.current.activityStatus).toBeNull()
    expect(result.current.activityElapsedSeconds).toBe(0)
    expect(result.current.isStreaming).toBe(false)
  })

  it('renders SSE rate_limit as an inline AI bubble with localized guidance', async () => {
    const { toast } = await import('@/lib/hooks/use-toast')

    const rateLimitStream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"error","error_code":"rate_limit","message":"Rate limit exceeded. Please wait a moment and try again."}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    sourceChatApiMock.sendMessage.mockResolvedValue(rateLimitStream)

    const { result } = renderHook(() => useSourceChat('source:1'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.currentSessionId).toBe('session:1'))

    await act(async () => {
      await result.current.sendMessage('Trigger rate_limit')
    })

    expect(toast.error).not.toHaveBeenCalled()
    const aiMessages = result.current.messages.filter((m) => m.type === 'ai')
    expect(aiMessages.length).toBe(1)
    const bubble = aiMessages[0].content
    expect(bubble).toContain('⚠️')
    expect(bubble).toContain('error_code=rate_limit')
    expect(bubble).toContain('_Server message_: Rate limit exceeded')
    // i18n template includes the guidance "rate-limited" / "switch to a different model".
    expect(bubble.toLowerCase()).toContain('rate-limited')
  })

  it('surfaces heartbeat events as awaitingModel activity with elapsed seconds', async () => {
    let release!: () => void
    const released = new Promise<void>((resolve) => {
      release = resolve
    })

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
                  'data: {"type":"heartbeat","stage":"awaiting_model","elapsed_ms":5000}\n\n',
                ),
              }
            }
            if (step === 2) {
              await released
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"ai_message","content":"hi"}\n\n' +
                  'data: {"type":"complete"}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    sourceChatApiMock.sendMessage.mockResolvedValue(heartbeatStream)

    const { result } = renderHook(() => useSourceChat('source:1'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.currentSessionId).toBe('session:1'))

    let sendPromise: Promise<void>
    await act(async () => {
      sendPromise = result.current.sendMessage('Hello?')
    })

    await waitFor(() => {
      expect(result.current.activityStatus).toBe('awaitingModel')
      expect(result.current.activityElapsedSeconds).toBeGreaterThan(0)
    })

    await act(async () => {
      release()
      await sendPromise!
    })

    expect(result.current.activityStatus).toBeNull()
    expect(result.current.activityElapsedSeconds).toBe(0)
  })
})
