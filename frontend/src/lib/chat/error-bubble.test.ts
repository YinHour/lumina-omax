import { describe, it, expect } from 'vitest'
import { buildErrorBubbleBody } from './error-bubble'

const templates = {
  errorLlmTimeoutPrefix: '⚠️ System notice: ',
  errorLlmTimeout: 'Model response timed out after {seconds}s. Try shrinking sources.',
  errorResearchStall: 'Research Agent made no effective progress. Narrow the question.',
  errorResearchHardTimeout:
    'Research Agent exceeded the overall limit of {seconds}s. Narrow the scope.',
  errorAuthentication: 'API key is invalid.',
  errorRateLimit: 'Rate-limited. Wait a minute.',
  errorConfiguration: 'No default model configured.',
  errorNetwork: 'Cannot reach the provider.',
  errorExternalService: 'Provider returned an error.',
  errorInvalidInput: 'Request rejected.',
  errorNotFound: 'Resource not found.',
  errorInternal: 'Internal error.',
  errorGeneric: 'Request did not complete.',
}

describe('buildErrorBubbleBody', () => {
  it('renders llm_timeout with seconds substituted into the template', () => {
    const { body, code } = buildErrorBubbleBody(
      {
        type: 'error',
        error_code: 'llm_timeout',
        timeout_seconds: 3,
        message: 'Model timed out after 3s.',
      },
      templates,
    )
    expect(code).toBe('llm_timeout')
    expect(body).toContain('⚠️')
    expect(body).toContain('timed out after 3s')
    expect(body).toContain('error_code=llm_timeout')
    expect(body).toContain('timeout_seconds=3')
    expect(body).toContain('_Server message_: Model timed out after 3s.')
  })

  it('renders authentication with localized guidance and diagnostic block', () => {
    const { body, code } = buildErrorBubbleBody(
      {
        type: 'error',
        error_code: 'authentication',
        message: 'Authentication failed. Check API key.',
      },
      templates,
    )
    expect(code).toBe('authentication')
    expect(body).toContain('API key is invalid.')
    expect(body).toContain('error_code=authentication')
    // No timeout_seconds for non-timeout codes.
    expect(body).not.toContain('timeout_seconds=')
  })

  it('renders research_stall with its own template and no seconds', () => {
    const { body, code } = buildErrorBubbleBody(
      {
        type: 'error',
        error_code: 'research_stall',
        message: 'Research Agent made no progress for 120s.',
      },
      templates,
    )
    expect(code).toBe('research_stall')
    expect(body).toContain('no effective progress')
    expect(body).toContain('error_code=research_stall')
    expect(body).not.toContain('timeout_seconds=')
  })

  it('renders research_hard_timeout with seconds substituted', () => {
    const { body, code } = buildErrorBubbleBody(
      {
        type: 'error',
        error_code: 'research_hard_timeout',
        timeout_seconds: 600,
        message: 'Research Agent exceeded the overall time limit.',
      },
      templates,
    )
    expect(code).toBe('research_hard_timeout')
    expect(body).toContain('limit of 600s')
    expect(body).toContain('error_code=research_hard_timeout')
    expect(body).toContain('timeout_seconds=600')
  })

  it('falls back to errorGeneric for unknown codes but still embeds server message', () => {
    const { body, code } = buildErrorBubbleBody(
      {
        type: 'error',
        error_code: 'some_new_code_we_dont_know',
        message: 'Bespoke upstream error.',
      },
      templates,
    )
    expect(code).toBe('some_new_code_we_dont_know')
    expect(body).toContain('Request did not complete.')
    expect(body).toContain('error_code=some_new_code_we_dont_know')
    expect(body).toContain('_Server message_: Bespoke upstream error.')
  })

  it('falls back to internal_error code when error_code field is missing', () => {
    const { body, code } = buildErrorBubbleBody(
      { type: 'error', message: 'Something went wrong.' },
      templates,
    )
    expect(code).toBe('internal_error')
    expect(body).toContain('Internal error.')
    expect(body).toContain('error_code=internal_error')
  })

  it('omits the server message line when payload has no message', () => {
    const { body } = buildErrorBubbleBody(
      { type: 'error', error_code: 'rate_limit' },
      templates,
    )
    expect(body).toContain('Rate-limited')
    expect(body).not.toContain('_Server message_')
  })
})
