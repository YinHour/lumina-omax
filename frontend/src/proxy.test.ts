import { NextRequest } from 'next/server'
import { describe, expect, it } from 'vitest'

import { proxy } from './proxy'

function request(path: string, cookie?: string) {
  return new NextRequest(`http://example.test${path}`, {
    headers: cookie ? { cookie } : undefined,
  })
}

describe('proxy', () => {
  it('redirects the root path to notebooks', () => {
    const response = proxy(request('/'))

    expect(response.status).toBe(307)
    expect(response.headers.get('location')).toBe('http://example.test/notebooks')
  })

  it('allows public paths without auth', () => {
    const response = proxy(request('/login'))

    expect(response.status).toBe(200)
    expect(response.headers.get('location')).toBeNull()
  })

  it('redirects private paths to login when no auth cookie is present', () => {
    const response = proxy(request('/sources'))

    expect(response.status).toBe(307)
    expect(response.headers.get('location')).toBe('http://example.test/login?redirect=%2Fsources')
  })

  it('allows private paths when the auth cookie is present', () => {
    const response = proxy(request('/sources', 'auth-token=test-token'))

    expect(response.status).toBe(200)
    expect(response.headers.get('location')).toBeNull()
  })
})
