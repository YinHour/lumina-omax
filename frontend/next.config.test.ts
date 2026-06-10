import { afterEach, describe, expect, it } from 'vitest'

import nextConfig from './next.config'

describe('Next.js API rewrite configuration', () => {
  afterEach(() => {
    delete process.env.INTERNAL_API_URL
  })

  it('targets the standard container API port by default', async () => {
    const rewrites = await nextConfig.rewrites?.()

    expect(rewrites).toEqual([
      {
        source: '/api/:path*',
        destination: 'http://localhost:5055/api/:path*',
      },
    ])
  })

  it('supports an explicit API address for parallel development', async () => {
    process.env.INTERNAL_API_URL = 'http://localhost:5056'

    const rewrites = await nextConfig.rewrites?.()

    expect(rewrites).toEqual([
      {
        source: '/api/:path*',
        destination: 'http://localhost:5056/api/:path*',
      },
    ])
  })
})
