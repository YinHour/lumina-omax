import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { AddExistingSourceDialog } from './AddExistingSourceDialog'
import { sourcesApi } from '@/lib/api/sources'
import type { SourceListResponse } from '@/lib/types/api'

const addSourcesMock = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
}))

const currentNotebookSourcesMock = vi.hoisted(() => ({
  data: [] as SourceListResponse[],
}))

vi.mock('@/lib/api/sources', () => ({
  sourcesApi: {
    list: vi.fn(),
  },
}))

vi.mock('@/lib/hooks/use-sources', async () => {
  const actual = await vi.importActual<typeof import('@/lib/hooks/use-sources')>('@/lib/hooks/use-sources')
  return {
    ...actual,
    useSources: () => ({ data: currentNotebookSourcesMock.data }),
    useAddSourcesToNotebook: () => ({
      mutateAsync: addSourcesMock.mutateAsync,
      isPending: false,
    }),
  }
})

vi.mock('@/lib/hooks/use-settings', () => ({
  useSettings: () => ({
    data: {
      source_batch_limit: 50,
    },
  }),
}))

vi.mock('@/lib/hooks/use-notebooks', () => ({
  useNotebook: () => ({
    data: {
      id: 'notebook:1',
      source_count: currentNotebookSourcesMock.data.length,
    },
  }),
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

const source = (overrides: Partial<SourceListResponse>): SourceListResponse => ({
  id: 'source:default',
  title: 'Default source',
  topics: [],
  asset: null,
  embedded: true,
  embedded_chunks: 4,
  kg_extracted: true,
  insights_count: 0,
  created: '2026-06-13T00:00:00Z',
  updated: '2026-06-13T00:00:00Z',
  notebook_count: 0,
  ...overrides,
})

describe('AddExistingSourceDialog source filtering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    currentNotebookSourcesMock.data = []
    vi.mocked(sourcesApi.list).mockResolvedValue({
      items: [
        source({
          id: 'source:embedded',
          title: 'Embedded Source',
          kg_extracted: false,
        }),
        source({
          id: 'source:embedded-kg',
          title: 'Embedded With KG Source',
          kg_extracted: true,
        }),
        source({
          id: 'source:pending',
          title: 'Unembedded Source',
          embedded: false,
          embedded_chunks: 0,
          kg_extracted: true,
        }),
      ],
      total: 3,
    })
  })

  it('shows only embedded sources when adding existing sources', async () => {
    render(
      <AddExistingSourceDialog
        open
        onOpenChange={vi.fn()}
        notebookId="notebook:1"
      />,
      { wrapper: createWrapper() },
    )

    await screen.findByText('Embedded Source')
    expect(screen.getByText('Embedded With KG Source')).toBeInTheDocument()
    expect(screen.queryByText('Unembedded Source')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('Select All'))
    expect(screen.getByText('2 sources selected')).toBeInTheDocument()
  })

  it('limits existing source selection by the remaining notebook source slots', async () => {
    currentNotebookSourcesMock.data = Array.from({ length: 49 }, (_, index) =>
      source({
        id: `source:current-${index}`,
        title: `Current Source ${index}`,
      }),
    )

    render(
      <AddExistingSourceDialog
        open
        onOpenChange={vi.fn()}
        notebookId="notebook:1"
      />,
      { wrapper: createWrapper() },
    )

    await screen.findByText('Embedded Source')

    fireEvent.click(screen.getByText('Select All'))

    expect(screen.getByText('1 sources selected')).toBeInTheDocument()
    expect(addSourcesMock.mutateAsync).not.toHaveBeenCalled()
  })
})
