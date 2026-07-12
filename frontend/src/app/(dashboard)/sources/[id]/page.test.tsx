import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SourceDetailPage from './page'

const routerPush = vi.hoisted(() => vi.fn())
const clearReturnTo = vi.hoisted(() => vi.fn())

vi.mock('react', async () => {
  const actual = await vi.importActual<typeof import('react')>('react')
  return {
    ...actual,
    use: () => ({ id: 'source:abc' }),
  }
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('@/lib/hooks/use-navigation', () => ({
  useNavigation: () => ({
    getReturnPath: () => '/sources',
    getReturnLabel: () => '',
    clearReturnTo,
  }),
}))

vi.mock('@/lib/hooks/use-translation', () => ({
  useTranslation: () => ({
    t: {
      common: { close: 'Close' },
      sources: {
        backToSources: 'Back to sources',
        sourceContent: 'Source content',
        expandSourceContent: 'Expand source content',
      },
    },
  }),
}))

vi.mock('@/lib/hooks/useSourceChat', () => ({
  useSourceChat: () => ({
    messages: [],
    isStreaming: false,
    activityStatus: null,
    activityElapsedSeconds: 0,
    contextIndicators: null,
    sendMessage: vi.fn(),
    currentSession: null,
    currentSessionId: null,
    updateSession: vi.fn(),
    sessions: [],
    createSession: vi.fn(),
    switchSession: vi.fn(),
    deleteSession: vi.fn(),
    loadingSessions: false,
    cancelStreaming: vi.fn(),
  }),
}))

vi.mock('@/components/source/SourceDetailContent', () => ({
  SourceDetailContent: ({
    onCollapse,
    showCloseButton,
  }: {
    onCollapse?: () => void
    showCloseButton?: boolean
  }) => (
    <div data-testid="source-detail-content" data-show-close={String(showCloseButton)}>
      <button type="button" onClick={onCollapse}>Collapse source content</button>
    </div>
  ),
}))

vi.mock('@/components/source/ChatPanel', () => ({
  ChatPanel: () => <div data-testid="source-chat-panel">Source chat</div>,
}))

describe('SourceDetailPage collapsible source column', () => {
  it('keeps chat, source state, and the page close action available while collapsed', () => {
    render(<SourceDetailPage params={Promise.resolve({ id: 'source:abc' })} />)

    const sourceColumn = screen.getByTestId('source-detail-column')
    expect(sourceColumn).not.toHaveClass('lg:hidden')
    expect(screen.getByTestId('source-detail-content')).toHaveAttribute('data-show-close', 'false')
    expect(screen.getByTestId('source-chat-panel')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse source content' }))

    expect(sourceColumn).toHaveClass('lg:hidden')
    expect(screen.getByRole('button', { name: 'Expand source content' })).toBeInTheDocument()
    expect(screen.getByTestId('source-detail-content')).toBeInTheDocument()
    expect(screen.getByTestId('source-chat-panel')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Expand source content' }))
    expect(sourceColumn).not.toHaveClass('lg:hidden')

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(routerPush).toHaveBeenCalledWith('/sources')
    expect(clearReturnTo).toHaveBeenCalledTimes(1)
  })
})
