import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import type { NotebookResponse } from '@/lib/types/api'
import NotebooksPage from './page'

const notebookData = vi.hoisted(() => ({
  active: [
    {
      id: 'notebook:mine-active',
      name: '我的活跃笔记本',
      description: '',
      archived: false,
      created: '2026-06-20T00:00:00Z',
      updated: '2026-06-20T00:00:00Z',
      source_count: 1,
      note_count: 0,
      password: null,
      creator_name: '王海东',
      created_by: 'user:abc123',
      is_aggregated: false,
      aggregated_notebooks: [],
    },
    {
      id: 'notebook:other-active',
      name: '别人的活跃笔记本',
      description: '',
      archived: false,
      created: '2026-06-20T00:00:00Z',
      updated: '2026-06-20T00:00:00Z',
      source_count: 1,
      note_count: 0,
      password: null,
      creator_name: '其他用户',
      created_by: 'user:someone-else',
      is_aggregated: false,
      aggregated_notebooks: [],
    },
    {
      id: 'notebook:mine-aggregated',
      name: '我的聚合笔记本',
      description: '',
      archived: false,
      created: '2026-06-20T00:00:00Z',
      updated: '2026-06-20T00:00:00Z',
      source_count: 2,
      note_count: 0,
      password: null,
      creator_name: '王海东',
      created_by: 'abc123',
      is_aggregated: true,
      aggregated_notebooks: [],
    },
    {
      id: 'notebook:other-aggregated',
      name: '别人的聚合笔记本',
      description: '',
      archived: false,
      created: '2026-06-20T00:00:00Z',
      updated: '2026-06-20T00:00:00Z',
      source_count: 2,
      note_count: 0,
      password: null,
      creator_name: '其他用户',
      created_by: 'someone-else',
      is_aggregated: true,
      aggregated_notebooks: [],
    },
  ] as NotebookResponse[],
  archived: [
    {
      id: 'notebook:mine-archived',
      name: '我的归档笔记本',
      description: '',
      archived: true,
      created: '2026-06-20T00:00:00Z',
      updated: '2026-06-20T00:00:00Z',
      source_count: 0,
      note_count: 0,
      password: null,
      creator_name: '王海东',
      created_by: 'user:abc123',
      is_aggregated: false,
      aggregated_notebooks: [],
    },
    {
      id: 'notebook:other-archived',
      name: '别人的归档笔记本',
      description: '',
      archived: true,
      created: '2026-06-20T00:00:00Z',
      updated: '2026-06-20T00:00:00Z',
      source_count: 0,
      note_count: 0,
      password: null,
      creator_name: '其他用户',
      created_by: 'user:someone-else',
      is_aggregated: false,
      aggregated_notebooks: [],
    },
  ] as NotebookResponse[],
}))

vi.mock('@/components/layout/AppShell', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock('@/components/layout/PageContainer', () => ({
  PageContainer: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}))

vi.mock('@/components/layout/PageHeader', () => ({
  PageHeader: ({
    title,
    actions,
  }: {
    title: string
    actions: ReactNode
  }) => (
    <header>
      <h1>{title}</h1>
      <div>{actions}</div>
    </header>
  ),
}))

vi.mock('./components/NotebookList', () => ({
  NotebookList: ({
    title,
    notebooks,
    emptyTitle,
    actionLabel,
  }: {
    title: string
    notebooks?: NotebookResponse[]
    emptyTitle?: string
    actionLabel?: string
  }) => (
    <section aria-label={title}>
      <h2>
        {title} ({notebooks?.length ?? 0})
      </h2>
      {actionLabel ? <button type="button">{actionLabel}</button> : null}
      {notebooks?.length
        ? notebooks.map((notebook) => <article key={notebook.id}>{notebook.name}</article>)
        : emptyTitle ? <p>{emptyTitle}</p> : null}
    </section>
  ),
}))

vi.mock('@/components/notebooks/CreateNotebookDialog', () => ({
  CreateNotebookDialog: () => null,
}))

vi.mock('@/components/notebooks/AggregateNotebookDialog', () => ({
  AggregateNotebookDialog: () => null,
}))

vi.mock('@/lib/hooks/use-notebooks', () => ({
  useNotebooks: (archived?: boolean) => ({
    data: archived ? notebookData.archived : notebookData.active,
    isLoading: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/lib/stores/auth-store', () => ({
  useAuthStore: (selector: (state: { user: unknown }) => unknown) =>
    selector({
      user: {
      id: 'user:abc123',
      username: 'leiw',
      display_name: '王海东',
      },
    }),
}))

vi.mock('@/lib/hooks/use-translation', () => ({
  useTranslation: () => ({
    t: {
      notebooks: {
        title: '笔记本',
        activeNotebooks: '活动的笔记本',
        aggregatedNotebooks: '聚合笔记本',
        archivedNotebooks: '归档笔记本',
        aggregateNotebook: '聚合笔记本',
        newNotebook: '创建笔记本',
        searchPlaceholder: '搜索笔记本...',
        showMineOnly: '只看我的',
        noOwnedNotebooks: '还没有你创建的笔记本',
      },
      common: {
        refresh: '刷新',
        noMatches: '无匹配项',
        tryDifferentSearch: '换个关键词试试',
        accessibility: { searchNotebooks: '搜索笔记本' },
      },
    },
  }),
}))

describe('NotebooksPage owner filter', () => {
  it('filters every notebook section to notebooks created by the current user', () => {
    render(<NotebooksPage />)

    expect(screen.getByText('我的活跃笔记本')).toBeInTheDocument()
    expect(screen.getByText('别人的活跃笔记本')).toBeInTheDocument()
    expect(screen.getByText('我的聚合笔记本')).toBeInTheDocument()
    expect(screen.getByText('别人的聚合笔记本')).toBeInTheDocument()
    expect(screen.getByText('我的归档笔记本')).toBeInTheDocument()
    expect(screen.getByText('别人的归档笔记本')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '只看我的' }))

    expect(screen.getByText('我的活跃笔记本')).toBeInTheDocument()
    expect(screen.queryByText('别人的活跃笔记本')).not.toBeInTheDocument()
    expect(screen.getByText('我的聚合笔记本')).toBeInTheDocument()
    expect(screen.queryByText('别人的聚合笔记本')).not.toBeInTheDocument()
    expect(screen.getByText('我的归档笔记本')).toBeInTheDocument()
    expect(screen.queryByText('别人的归档笔记本')).not.toBeInTheDocument()
  })

  it('combines owner filtering with notebook name search', () => {
    render(<NotebooksPage />)

    fireEvent.click(screen.getByRole('button', { name: '只看我的' }))
    fireEvent.change(screen.getByLabelText('搜索笔记本'), {
      target: { value: '聚合' },
    })

    expect(screen.queryByText('我的活跃笔记本')).not.toBeInTheDocument()
    expect(screen.getByText('我的聚合笔记本')).toBeInTheDocument()
    expect(screen.queryByText('别人的聚合笔记本')).not.toBeInTheDocument()
  })
})
