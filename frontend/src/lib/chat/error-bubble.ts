/**
 * Stable wire identifiers for chat / source-chat / ask SSE error events.
 *
 * Mirrors `api.sse_helpers.ERROR_CODE_BY_EXCEPTION_NAME`. Keep additive: the
 * front-end falls back to `errorGeneric` for any unknown code so a backend
 * adding a new code in the future does not crash the UI.
 */
export type ChatErrorCode =
  | 'llm_timeout'
  | 'authentication'
  | 'rate_limit'
  | 'configuration'
  | 'network'
  | 'external_service'
  | 'invalid_input'
  | 'not_found'
  | 'internal_error'

export interface ErrorBubbleTemplates {
  errorLlmTimeoutPrefix: string
  errorLlmTimeout: string
  errorAuthentication: string
  errorRateLimit: string
  errorConfiguration: string
  errorNetwork: string
  errorExternalService: string
  errorInvalidInput: string
  errorNotFound: string
  errorInternal: string
  errorGeneric: string
}

export interface ChatErrorPayload {
  type?: string
  error_code?: string
  message?: string
  timeout_seconds?: number
}

export interface BuiltErrorBubble {
  body: string
  code: string
}

/**
 * Build the markdown body for an inline error bubble. The result follows the
 * §29.7 layout:
 *
 *   ⚠️ <prefix><localized title>\n
 *      <localized guidance>\n
 *   ---\n
 *   _Diagnostic_: `error_code=<x>[, timeout_seconds=<n>]`\n
 *   _Server message_: <original server-side classified message>
 *
 * The diagnostic block is intentionally English and kept verbatim so users
 * can paste it back to the team when reporting issues.
 */
export function buildErrorBubbleBody(
  data: ChatErrorPayload,
  templates: ErrorBubbleTemplates,
): BuiltErrorBubble {
  const code = typeof data.error_code === 'string' && data.error_code
    ? data.error_code
    : 'internal_error'

  const seconds = typeof data.timeout_seconds === 'number'
    ? Math.round(data.timeout_seconds)
    : null

  const codeTemplates: Partial<Record<string, string>> = {
    llm_timeout: templates.errorLlmTimeout,
    authentication: templates.errorAuthentication,
    rate_limit: templates.errorRateLimit,
    configuration: templates.errorConfiguration,
    network: templates.errorNetwork,
    external_service: templates.errorExternalService,
    invalid_input: templates.errorInvalidInput,
    not_found: templates.errorNotFound,
    internal_error: templates.errorInternal,
  }

  const template = codeTemplates[code] ?? templates.errorGeneric
  const localized = seconds !== null
    ? template.replace('{seconds}', String(seconds))
    : template.replace('{seconds}', '')

  const diagnosticParts = [
    `error_code=${code}`,
    seconds !== null ? `timeout_seconds=${seconds}` : null,
  ].filter(Boolean).join(', ')
  const diagnosticLine = `_Diagnostic_: \`${diagnosticParts}\``
  const serverLine = data.message ? `_Server message_: ${data.message}` : ''

  const body = [
    `${templates.errorLlmTimeoutPrefix}${localized}`,
    '',
    '---',
    '',
    diagnosticLine,
    serverLine,
  ].filter(Boolean).join('\n')

  return { body, code }
}
