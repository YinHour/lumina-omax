import type { NextRequest } from 'next/server'

const FORWARDED_REQUEST_HEADERS = [
  'accept',
  'authorization',
  'content-type',
  'cookie',
  'traceparent',
  'tracestate',
  'x-open-notebook-password',
] as const

function internalApiBaseUrl(): string {
  return (process.env.INTERNAL_API_URL || 'http://localhost:5055').replace(/\/+$/, '')
}

export async function proxySsePost(
  request: NextRequest,
  apiPath: string,
): Promise<Response> {
  const requestUrl = new URL(request.url)
  const upstreamUrl = new URL(`${internalApiBaseUrl()}${apiPath}`)
  upstreamUrl.search = requestUrl.search

  const upstreamHeaders = new Headers()
  for (const headerName of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(headerName)
    if (value) {
      upstreamHeaders.set(headerName, value)
    }
  }
  upstreamHeaders.set('accept', 'text/event-stream')

  const upstreamResponse = await fetch(upstreamUrl, {
    method: 'POST',
    headers: upstreamHeaders,
    body: await request.arrayBuffer(),
    cache: 'no-store',
    signal: request.signal,
  })

  const responseHeaders = new Headers({
    'Cache-Control': 'no-cache, no-transform',
    'Content-Type':
      upstreamResponse.headers.get('content-type') ||
      'text/event-stream; charset=utf-8',
    'X-Accel-Buffering': 'no',
  })

  const requestId = upstreamResponse.headers.get('x-request-id')
  if (requestId) {
    responseHeaders.set('X-Request-Id', requestId)
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  })
}
