import type { NextRequest } from 'next/server'

import { proxySsePost } from '@/lib/server/sse-proxy'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

interface SourceChatRouteContext {
  params: Promise<{
    sourceId: string
    sessionId: string
  }>
}

export async function POST(
  request: NextRequest,
  context: SourceChatRouteContext,
) {
  const { sourceId, sessionId } = await context.params
  return proxySsePost(
    request,
    `/api/sources/${encodeURIComponent(sourceId)}/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
  )
}
