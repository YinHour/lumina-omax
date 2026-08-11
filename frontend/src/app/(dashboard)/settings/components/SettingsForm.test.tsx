import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { SettingsForm } from './SettingsForm'

// Hoisted mutable settings so individual tests can vary the GET response.
const state = vi.hoisted(() => {
  const MASKED = '*'.repeat(20)
  return {
    MASKED,
    settings: {
      default_content_processing_engine_doc: 'auto' as string | undefined,
      default_content_processing_engine_url: 'firecrawl',
      default_embedding_option: 'ask',
      auto_delete_files: 'yes',
      source_batch_limit: 50,
      tavily_api_key: MASKED,
      tavily_include_domains: 'example.com',
      firecrawl_api_key: MASKED,
    },
  }
})

const MASKED = state.MASKED

const updateSettingsMock = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}))

vi.mock('@/lib/hooks/use-settings', () => ({
  useSettings: () => ({
    data: state.settings,
    isLoading: false,
    isFetching: false,
    error: null,
  }),
  useUpdateSettings: () => ({
    mutateAsync: updateSettingsMock.mutateAsync,
    isPending: false,
  }),
}))

vi.mock('sonner', () => ({
  toast: vi.fn(),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  return Wrapper
}

describe('SettingsForm', () => {
  beforeEach(() => {
    updateSettingsMock.mutateAsync.mockReset()
    // Restore a configured baseline between tests.
    state.settings = {
      default_content_processing_engine_doc: 'auto',
      default_content_processing_engine_url: 'firecrawl',
      default_embedding_option: 'ask',
      auto_delete_files: 'yes',
      source_batch_limit: 50,
      tavily_api_key: MASKED,
      tavily_include_domains: 'example.com',
      firecrawl_api_key: MASKED,
    }
  })

  it('populates the Firecrawl API Key field with the masked sentinel (configured indicator)', async () => {
    render(<SettingsForm />, { wrapper: createWrapper() })

    const input = screen.getByLabelText('Firecrawl API Key') as HTMLInputElement
    expect(input).toBeInTheDocument()
    expect(input.type).toBe('password')
    // The raw key is never sent to the browser; the masked sentinel is shown instead.
    expect(input.value).toBe(MASKED)
  })

  it('submits a newly typed Firecrawl API Key', async () => {
    updateSettingsMock.mutateAsync.mockResolvedValue({})
    render(<SettingsForm />, { wrapper: createWrapper() })

    const input = screen.getByLabelText('Firecrawl API Key') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'fc-new-key' } })
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))

    await waitFor(() => {
      expect(updateSettingsMock.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ firecrawl_api_key: 'fc-new-key' })
      )
    })
  })

  it('sends null for unchanged secret fields when saving an unrelated change (no wipe)', async () => {
    updateSettingsMock.mutateAsync.mockResolvedValue({})
    render(<SettingsForm />, { wrapper: createWrapper() })

    // Change an unrelated field so the form becomes dirty and Save is enabled.
    const limitInput = screen.getByLabelText(/limit/i) as HTMLInputElement
    fireEvent.change(limitInput, { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: /settings/i }))

    await waitFor(() => {
      expect(updateSettingsMock.mutateAsync).toHaveBeenCalledTimes(1)
    })
    const payload = updateSettingsMock.mutateAsync.mock.calls[0][0]
    // Unchanged secrets are sent as null so the backend skips them (no overwrite).
    expect(payload.firecrawl_api_key).toBeNull()
    expect(payload.tavily_api_key).toBeNull()
    // The whitelisted domains field is also unchanged -> null.
    expect(payload.tavily_include_domains).toBeNull()
    // The actually-changed field is sent.
    expect(payload.source_batch_limit).toBe(100)
  })

  it('populates the form even when default_content_processing_engine_doc is null (reset-guard fix)', async () => {
    // Simulate the env-fallback case where the doc engine field is absent in the DB.
    state.settings = {
      ...state.settings,
      default_content_processing_engine_doc: undefined,
      firecrawl_api_key: MASKED,
    }
    render(<SettingsForm />, { wrapper: createWrapper() })

    const input = screen.getByLabelText('Firecrawl API Key') as HTMLInputElement
    // The form must still populate from GET; previously the reset never fired and
    // the field stayed on its empty default, causing wipes on save.
    expect(input.value).toBe(MASKED)
  })
})
