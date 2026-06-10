import { NextRequest } from 'next/server'
import { afterEach, describe, expect, it } from 'vitest'

import { GET } from './route'

describe('runtime config route', () => {
  afterEach(() => {
    delete process.env.API_URL
    delete process.env.NEXT_PUBLIC_API_URL
  })

  it('uses the standard API port when auto-detecting the public URL', async () => {
    const request = new NextRequest('http://example.test/config', {
      headers: { host: 'example.test:8502' },
    })

    const response = await GET(request)

    await expect(response.json()).resolves.toEqual({
      apiUrl: 'http://example.test:5055',
    })
  })

  it('uses API_URL when a deployment provides an explicit public URL', async () => {
    process.env.API_URL = 'http://example.test:5056'
    const request = new NextRequest('http://example.test/config')

    const response = await GET(request)

    await expect(response.json()).resolves.toEqual({
      apiUrl: 'http://example.test:5056',
    })
  })
})
