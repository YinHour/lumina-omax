import { NextRequest } from 'next/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { proxySsePost } from './sse-proxy'

describe('SSE route proxy', () => {
  afterEach(() => {
    delete process.env.INTERNAL_API_URL
    vi.restoreAllMocks()
  })

  it('forwards authentication and exposes upstream chunks before completion', async () => {
    process.env.INTERNAL_API_URL = 'http://api.internal:5056'
    let upstreamController: ReadableStreamDefaultController<Uint8Array> | null = null
    const upstreamBody = new ReadableStream<Uint8Array>({
      start(controller) {
        upstreamController = controller
      },
    })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(upstreamBody, {
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    )
    const request = new NextRequest('http://browser.test/api/chat/execute', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer test-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: 'hello' }),
    })

    const response = await proxySsePost(request, '/api/chat/execute')
    const reader = response.body!.getReader()
    const firstRead = reader.read()
    upstreamController!.enqueue(
      new TextEncoder().encode('data: {"type":"ai_message","content":"Hi"}\n\n'),
    )

    await expect(firstRead).resolves.toMatchObject({ done: false })
    expect(fetchMock).toHaveBeenCalledWith(
      new URL('http://api.internal:5056/api/chat/execute'),
      expect.objectContaining({
        method: 'POST',
        cache: 'no-store',
      }),
    )
    const forwardedHeaders = fetchMock.mock.calls[0][1]?.headers as Headers
    expect(forwardedHeaders.get('authorization')).toBe('Bearer test-token')
    expect(response.headers.get('cache-control')).toBe('no-cache, no-transform')
    expect(response.headers.get('x-accel-buffering')).toBe('no')

    upstreamController!.close()
  })
})
