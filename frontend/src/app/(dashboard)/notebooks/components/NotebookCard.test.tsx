import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { useAuthStore } from '@/lib/stores/auth-store'
import { NotebookCard } from './NotebookCard'
import type { NotebookResponse } from '@/lib/types/api'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/lib/hooks/use-notebooks', () => ({
  useUpdateNotebook: () => ({ mutate: vi.fn(), mutateAsync: vi.fn() }),
  useDeleteNotebook: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useNotebookDeletePreview: () => ({ data: null, isLoading: false }),
  useManageNotebookPassword: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateNotebookPassword: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

const notebook: NotebookResponse = {
  id: 'notebook:1',
  name: 'Owned notebook',
  description: 'desc',
  archived: false,
  created: '2026-06-12T00:00:00Z',
  updated: '2026-06-12T00:00:00Z',
  source_count: 0,
  note_count: 0,
  password: null,
  creator_name: 'Alice',
  created_by: 'user:abc123',
  is_aggregated: false,
  aggregated_notebooks: [],
}

describe('NotebookCard', () => {
  beforeEach(() => {
    useAuthStore.setState({
      isAuthenticated: true,
      user: {
        id: 'abc123',
        username: 'alice',
        display_name: 'Alice',
      },
    })
  })

  it('shows management menu when notebook creator is returned as a record id', () => {
    render(<NotebookCard notebook={notebook} />, { wrapper: createWrapper() })

    expect(screen.getByRole('button', { name: 'More actions' })).toBeInTheDocument()
  })

  it('shows management menu when notebook creator is returned as a Surreal record object', () => {
    render(
      <NotebookCard
        notebook={{
          ...notebook,
          created_by: { id: 'user:abc123' } as unknown as string,
        }}
      />,
      { wrapper: createWrapper() },
    )

    expect(screen.getByRole('button', { name: 'More actions' })).toBeInTheDocument()
  })

  it('keeps owner actions visible and hides them for other users', () => {
    const { rerender } = render(<NotebookCard notebook={notebook} />, { wrapper: createWrapper() })

    expect(screen.getByRole('button', { name: 'More actions' })).not.toHaveClass('opacity-0')

    rerender(<NotebookCard notebook={{ ...notebook, created_by: 'user:someone-else' }} />)

    expect(screen.queryByRole('button', { name: 'More actions' })).not.toBeInTheDocument()
  })
})
