import { describe, expect, it, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

  it('renders a source-level close button when used inside the source modal', async () => {
    const onClose = vi.fn()
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

    renderWithQueryClient(<SourceDetailContent sourceId="source:abc" onClose={onClose} />)

    await waitFor(() => {
      expect(screen.getByText('Example source')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders standalone image before the image description content', async () => {
    vi.mocked(sourcesApi.get).mockResolvedValue({
      id: 'source:abc',
      title: 'Image source',
      full_text: '图像类型：lab_photo\n可确认信息：\n- 图片显示实验装置',
      asset: { file_path: '/data/uploads/example.png' },
      embedded: true,
      topics: [],
      created: '2026-06-08T00:00:00.000Z',
      updated: '2026-06-08T00:00:00.000Z',
      notebooks: [],
      file_available: true,
    } as never)

    renderWithQueryClient(<SourceDetailContent sourceId="source:abc" />)

    await waitFor(() => {
      expect(screen.getByText('Image source')).toBeInTheDocument()
    })

    const image = screen.getByRole('img', { name: 'Image source' })
    expect(image).toHaveAttribute('src', '/api/sources/source%3Aabc/download')
    const description = Array.from(document.querySelectorAll('p')).find(element =>
      element.textContent?.includes('图像类型：lab_photo')
    )
    expect(description).toBeTruthy()
    expect(image.compareDocumentPosition(description) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('uses the PNG preview endpoint for standalone TIFF images', async () => {
    vi.mocked(sourcesApi.get).mockResolvedValue({
      id: 'source:abc',
      title: 'TIFF source',
      full_text: '## Extracted Images\n\n![](/api/uploads/images/abc/example.tiff)\n\n## Figure Descriptions\n\nDescription unavailable.',
      asset: { file_path: '/data/uploads/example.tiff' },
      embedded: false,
      topics: [],
      created: '2026-06-08T00:00:00.000Z',
      updated: '2026-06-08T00:00:00.000Z',
      notebooks: [],
      file_available: true,
    } as never)

    renderWithQueryClient(<SourceDetailContent sourceId="source:abc" />)

    await waitFor(() => {
      expect(screen.getByText('TIFF source')).toBeInTheDocument()
    })

    const images = Array.from(document.querySelectorAll('img'))
    expect(images[0]).toHaveAttribute('src', '/api/sources/source%3Aabc/preview')
    expect(images[1]).toHaveAttribute('src', '/api/sources/source%3Aabc/preview')
  })
})
