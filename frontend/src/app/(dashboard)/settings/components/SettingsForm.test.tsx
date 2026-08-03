import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { SettingsForm } from './SettingsForm'

const updateSettingsMock = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}))

vi.mock('@/lib/hooks/use-settings', () => ({
  useSettings: () => ({
    data: {
      default_content_processing_engine_doc: 'auto',
      default_content_processing_engine_url: 'firecrawl',
      default_embedding_option: 'ask',
      auto_delete_files: 'yes',
      source_batch_limit: 50,
      tavily_api_key: '',
      tavily_include_domains: '',
      firecrawl_api_key: 'fc-test-key',
    },
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
  })

  it('renders the Firecrawl API Key input with the stored value', async () => {
    render(<SettingsForm />, { wrapper: createWrapper() })

    const input = screen.getByLabelText('Firecrawl API Key') as HTMLInputElement
    expect(input).toBeInTheDocument()
    expect(input.type).toBe('password')
    expect(input.value).toBe('fc-test-key')
  })

  it('submits the Firecrawl API Key with the settings form', async () => {
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
})
