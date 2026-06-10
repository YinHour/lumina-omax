import { NextRequest, NextResponse } from 'next/server'

/**
 * Runtime Configuration Endpoint
 *
 * This endpoint provides server-side environment variables to the client at runtime.
 * This solves the NEXT_PUBLIC_* limitation where variables are baked into the build.
 *
 * Environment Variables:
 * - API_URL: Where the browser/client should make API requests (public/external URL)
 * - INTERNAL_API_URL: Where Next.js server-side should proxy API requests (internal URL)
 *   Default: http://localhost:5055 (used by Next.js rewrites in next.config.ts)
 *
 * Why two different variables?
 * - API_URL: Used by browser clients, can be https://your-domain.com or http://server-ip:5055
 * - INTERNAL_API_URL: Used by Next.js rewrites for server-side proxying, typically http://localhost:5055
 *
 * Resolution logic for API_URL:
 * 1. If API_URL env var is set, use it (explicit override)
 * 2. Otherwise, return an empty URL so browser requests use Next.js rewrites
 *
 * This keeps the backend private on the host while allowing LAN users to access
 * the application through the frontend port only.
 */
export async function GET(_request: NextRequest) {
  // Priority 1: Check if API_URL is explicitly set
  const envApiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL

  if (envApiUrl) {
    return NextResponse.json({
      apiUrl: envApiUrl,
    })
  }

  // Use relative /api paths so the browser talks only to the frontend server.
  console.log('[runtime-config] Using relative API paths through Next.js rewrites')
  return NextResponse.json({
    apiUrl: '',
  })
}
