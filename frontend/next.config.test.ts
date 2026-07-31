import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'

import nextConfig from './next.config'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))

describe('Next.js development safety configuration', () => {
  it('uses Webpack for the default development server', () => {
    const packageJson = JSON.parse(
      readFileSync(path.join(frontendRoot, 'package.json'), 'utf8'),
    ) as { scripts?: { dev?: string } }

    expect(packageJson.scripts?.dev).toBe('next dev --webpack')
  })

  it('pins explicit Turbopack runs to the frontend package', () => {
    expect(nextConfig.turbopack?.root).toBe(frontendRoot)
  })
})

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
