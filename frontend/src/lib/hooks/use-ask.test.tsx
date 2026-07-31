import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAsk } from './use-ask'
import { useAskStore } from '@/lib/stores/ask-store'

const searchApiMock = vi.hoisted(() => ({
  askKnowledgeBase: vi.fn(),
}))

vi.mock('@/lib/api/search', () => ({
  searchApi: searchApiMock,
}))

vi.mock('@/lib/hooks/use-toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const models = {
  strategy: 'model:strategy',
  answer: 'model:answer',
  finalAnswer: 'model:final',
}

describe('useAsk', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAskStore.getState().clearState()
    useAskStore.getState().clearHistory()
  })

  it('sets local progress before reading the first server event', async () => {
    const stream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              expect(setProgressSpy).toHaveBeenCalledWith({
                stage: 'received',
                elapsedSeconds: 0,
                terminal: null,
              })
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    const setProgressSpy = vi.spyOn(useAskStore.getState(), 'setProgress')
    searchApiMock.askKnowledgeBase.mockResolvedValue(stream)

    const { result } = renderHook(() => useAsk())

    await act(async () => {
      await result.current.sendAsk('Hello?', models)
    })

    setProgressSpy.mockRestore()
  })

  it('updates Ask progress from status and heartbeat events', async () => {
    const stream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"status","stage":"planning","elapsed_ms":1200}\n\n' +
                  'data: {"type":"heartbeat","stage":"planning","elapsed_ms":5000}\n\n' +
                  'data: {"type":"status","stage":"searching","elapsed_ms":6000}\n\n' +
                  'data: {"type":"final_answer_delta","content":"dra"}\n\n' +
                  'data: {"type":"final_answer_delta","content":"ft"}\n\n' +
                  'data: {"type":"final_answer","content":"final"}\n\n' +
                  'data: {"type":"complete","final_answer":"final"}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    searchApiMock.askKnowledgeBase.mockResolvedValue(stream)

    const { result } = renderHook(() => useAsk())

    await act(async () => {
      await result.current.sendAsk('Hello?', models)
    })

    expect(result.current.finalAnswer).toBe('final')
    expect(result.current.progress?.stage).toBe('writing')
    expect(result.current.progress?.terminal).toBe('complete')
    expect(result.current.progress?.elapsedSeconds).toBe(6)
  })

  it('surfaces SSE llm_timeout as errorBubble (not a toast)', async () => {
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
                  'data: {"type":"coverage","total_sources":10,"embedded_sources":8}\n\n' +
                  'data: {"type":"error","error_code":"llm_timeout","timeout_seconds":3,"message":"Ask timed out after 3s."}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    searchApiMock.askKnowledgeBase.mockResolvedValue(timeoutStream)

    const { result } = renderHook(() => useAsk())

    await act(async () => {
      await result.current.sendAsk('Hello?', models)
    })

    expect(toast.error).not.toHaveBeenCalled()
    expect(result.current.errorBubble).toBeTruthy()
    expect(result.current.errorBubble).toContain('⚠️')
    expect(result.current.errorBubble).toContain('error_code=llm_timeout')
    expect(result.current.errorBubble!.toLowerCase()).toContain('timed out')
    expect(result.current.activityElapsedSeconds).toBe(0)
    expect(result.current.isStreaming).toBe(false)
  })

  it('updates activityElapsedSeconds on heartbeat events', async () => {
    const stream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"coverage","total_sources":1,"embedded_sources":1}\n\n' +
                  'data: {"type":"heartbeat","stage":"awaiting_model","elapsed_ms":7000}\n\n' +
                  'data: {"type":"final_answer","content":"final"}\n\n' +
                  'data: {"type":"complete","final_answer":"final"}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    searchApiMock.askKnowledgeBase.mockResolvedValue(stream)

    const { result } = renderHook(() => useAsk())

    await act(async () => {
      await result.current.sendAsk('Hello?', models)
    })

    expect(result.current.finalAnswer).toBe('final')
    // Elapsed counter resets to 0 once the stream completes — covered by
    // `setStreaming(false)` path.
    expect(result.current.activityElapsedSeconds).toBe(0)
  })

  it('renders SSE rate_limit as errorBubble with localized guidance', async () => {
    const { toast } = await import('@/lib/hooks/use-toast')

    const stream = {
      getReader: () => {
        let step = 0
        return {
          read: vi.fn(async () => {
            step += 1
            if (step === 1) {
              return {
                done: false,
                value: new TextEncoder().encode(
                  'data: {"type":"coverage","total_sources":1,"embedded_sources":1}\n\n' +
                  'data: {"type":"error","error_code":"rate_limit","message":"Rate limit exceeded."}\n\n',
                ),
              }
            }
            return { done: true, value: undefined }
          }),
        }
      },
    } as unknown as ReadableStream<Uint8Array>
    searchApiMock.askKnowledgeBase.mockResolvedValue(stream)

    const { result } = renderHook(() => useAsk())

    await act(async () => {
      await result.current.sendAsk('Hello?', models)
    })

    expect(toast.error).not.toHaveBeenCalled()
    expect(result.current.errorBubble).toBeTruthy()
    expect(result.current.errorBubble).toContain('error_code=rate_limit')
    expect(result.current.errorBubble).toContain('_Server message_: Rate limit exceeded')
    await waitFor(() => expect(result.current.isStreaming).toBe(false))
  })
})
