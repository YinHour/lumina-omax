import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { SourcesColumn } from './SourcesColumn'
import type { SourceListResponse } from '@/lib/types/api'
import type { ContextMode } from '../[id]/page'

const navigationMocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  setReturnTo: vi.fn(),
}))

vi.mock('@/components/sources/SourceCard', () => ({
  SourceCard: ({
    source,
    onClick,
  }: {
    source: SourceListResponse
    onClick?: (sourceId: string) => void
  }) => (
    <button type="button" data-testid="source-card" onClick={() => onClick?.(source.id)}>
      {source.title}
    </button>
  ),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: navigationMocks.routerPush }),
  usePathname: () => '/notebooks/notebook%3A1',
}))

vi.mock('@/components/sources/AddSourceDialog', () => ({
  AddSourceDialog: () => null,
}))

vi.mock('@/components/sources/AddExistingSourceDialog', () => ({
  AddExistingSourceDialog: () => null,
}))

vi.mock('@/components/common/ConfirmDialog', () => ({
  ConfirmDialog: () => null,
}))

vi.mock('@/lib/hooks/use-sources', () => ({
  useDeleteSource: () => ({ mutateAsync: vi.fn() }),
  useRetrySource: () => ({ mutateAsync: vi.fn() }),
  useRemoveSourceFromNotebook: () => ({ mutateAsync: vi.fn() }),
}))

vi.mock('@/lib/hooks/use-navigation', () => ({
  useNavigation: () => ({ setReturnTo: navigationMocks.setReturnTo }),
}))

vi.mock('@/lib/stores/notebook-columns-store', () => ({
  useNotebookColumnsStore: () => ({
    sourcesCollapsed: false,
    toggleSources: vi.fn(),
  }),
}))

vi.mock('@/lib/stores/auth-store', () => ({
  useAuthStore: () => ({ id: 'user:admin' }),
}))

vi.mock('@/lib/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

vi.mock('@/lib/hooks/use-translation', () => ({
  useTranslation: () => ({
    language: 'zh-CN',
    t: {
      navigation: { sources: '来源', notebooks: '笔记本' },
      sources: {
        addSource: '添加来源',
        addExistingTitle: '添加现有来源',
        selectedCount: '已选择 {count} 个来源',
        totalItems: '共 {count} 条',
        filterSources: '筛选来源...',
        searchPlaceholder: '搜索来源',
        noSourcesYet: '暂无来源',
        createFirstSource: '创建第一个来源',
        noSourcesMatchSearch: '未找到匹配的来源',
        selectAll: '全选',
        deselectAll: '取消全选',
        setAllFullText: '全部设为参考全文',
        setAllInsights: '全部设为参考见解',
        setAllToOff: '全部设为不参考',
        delete: '删除',
        deleteConfirm: '确认删除',
        failedToDeleteSource: '删除失败',
      },
      common: {
        error: '错误',
        cancel: '取消',
        delete: '删除',
        adminPasswordRequired: '需要管理员密码',
      },
      notebooks: { enterPassword: '请输入密码' },
    },
  }),
}))

const sources = [
  {
    id: 'source:alpha',
    title: 'Alpha Cement Report',
    topics: [],
    asset: { file_path: '/uploads/alpha.pdf' },
    embedded: true,
    insights_count: 1,
    created: '2026-06-13T00:00:00Z',
    updated: '2026-06-13T00:00:00Z',
  },
  {
    id: 'source:beta',
    title: 'Beta Additive Notes',
    topics: [],
    asset: { file_path: '/uploads/beta.pdf' },
    embedded: true,
    insights_count: 0,
    created: '2026-06-13T00:00:00Z',
    updated: '2026-06-13T00:00:00Z',
  },
] as SourceListResponse[]

describe('SourcesColumn context selection controls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('selects only the currently filtered sources for notebook chat context', () => {
    const onBulkContextModeChange = vi.fn()
    const contextSelections: Record<string, ContextMode> = {
      'source:alpha': 'off',
      'source:beta': 'off',
    }

    render(
      <SourcesColumn
        sources={sources}
        isLoading={false}
        notebookId="notebook:1"
        contextSelections={contextSelections}
        onContextModeChange={vi.fn()}
        onBulkContextModeChange={onBulkContextModeChange}
      />,
    )

    expect(document.body).toHaveTextContent('已选择 0 个来源')
    expect(document.body).toHaveTextContent('共 2 条')

    fireEvent.change(screen.getByPlaceholderText('筛选来源...'), {
      target: { value: 'alpha' },
    })

    expect(screen.getByText('Alpha Cement Report')).toBeInTheDocument()
    expect(screen.queryByText('Beta Additive Notes')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '全选' }))

    expect(onBulkContextModeChange).toHaveBeenCalledWith('full', ['source:alpha'])
  })

  it('opens notebook sources through the full source detail page', () => {
    render(
      <SourcesColumn
        sources={sources}
        isLoading={false}
        notebookId="notebook:1"
        notebookName="Notebook One"
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Alpha Cement Report' }))

    expect(navigationMocks.setReturnTo).toHaveBeenCalledWith(
      '/notebooks/notebook%3A1',
      'Notebook One',
      { highlightItemId: 'source:alpha' }
    )
    expect(navigationMocks.routerPush).toHaveBeenCalledWith('/sources/source:alpha')
  })
})
