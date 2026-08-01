import type { NextRequest } from 'next/server'

import { proxySsePost } from '@/lib/server/sse-proxy'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

export async function POST(request: NextRequest) {
  return proxySsePost(request, '/api/chat/research/execute')
}
