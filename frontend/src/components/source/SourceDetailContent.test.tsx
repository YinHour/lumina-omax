import { describe, expect, it, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { SourceDetailContent } from './SourceDetailContent'
import { sourcesApi } from '@/lib/api/sources'
import { insightsApi } from '@/lib/api/insights'
import { transformationsApi } from '@/lib/api/transformations'

vi.mock('@/lib/api/sources', () => ({
  sourcesApi: {
    get: vi.fn(),
    downloadFile: vi.fn(),
    downloadMarkdown: vi.fn(),
    downloadPackage: vi.fn(),
  },
}))

vi.mock('@/lib/api/insights', () => ({
  insightsApi: {
    listForSource: vi.fn(),
  },
}))

vi.mock('@/lib/api/transformations', () => ({
  transformationsApi: {
    list: vi.fn(),
  },
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

describe('SourceDetailContent header', () => {
  beforeEach(() => {
    vi.mocked(insightsApi.listForSource).mockResolvedValue([])
    vi.mocked(transformationsApi.list).mockResolvedValue([])
  })

  it('renders the translated source type instead of the raw file enum', async () => {
    vi.mocked(sourcesApi.get).mockResolvedValue({
      id: 'source:abc',
      title: 'Example source',
      full_text: 'Content',
      asset: { file_path: 'uploads/example.pdf' },
      embedded: true,
      topics: [],
      created: '2026-06-08T00:00:00.000Z',
      updated: '2026-06-08T00:00:00.000Z',
      notebooks: [],
      file_available: true,
    } as never)

    renderWithQueryClient(<SourceDetailContent sourceId="source:abc" />)

    await waitFor(() => {
      expect(screen.getByText('Example source')).toBeInTheDocument()
    })

    expect(screen.getByText('File')).toBeInTheDocument()
    expect(screen.queryByText('file')).not.toBeInTheDocument()
  })

  it('renders an accessible actions menu for processed content downloads', async () => {
    vi.mocked(sourcesApi.get).mockResolvedValue({
      id: 'source:abc',
      title: 'Example source',
      full_text: '# Parsed content',
      asset: { file_path: 'uploads/example.pdf' },
      embedded: true,
      topics: [],
      created: '2026-06-08T00:00:00.000Z',
      updated: '2026-06-08T00:00:00.000Z',
      notebooks: [],
      file_available: true,
    } as never)

    renderWithQueryClient(<SourceDetailContent sourceId="source:abc" />)

    await waitFor(() => {
      expect(screen.getByText('Example source')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: 'More actions' })).toBeInTheDocument()
  })
})
