import { render, screen } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { ChatColumn } from './ChatColumn'
import { useNotes } from '@/lib/hooks/use-notes'
import { useNotebookChat } from '@/lib/hooks/useNotebookChat'
import { useNotebookGuide, useRegenerateNotebookGuide } from '@/lib/hooks/use-notebooks'
import { useModelDefaults, useModels } from '@/lib/hooks/use-models'

const { chatPanelMock } = vi.hoisted(() => ({
  chatPanelMock: vi.fn(),
}))

// Mock the hooks
vi.mock('@/lib/hooks/use-notes')
vi.mock('@/lib/hooks/useNotebookChat')
vi.mock('@/lib/hooks/use-notebooks')
vi.mock('@/lib/hooks/use-models')
vi.mock('@/components/source/ChatPanel', () => ({
  ChatPanel: (props: unknown) => {
    chatPanelMock(props)
    return <div data-testid="chat-panel" />
  }
}))

// Type-safe mock factory for useNotes hook
function createNotesMock(overrides: { isLoading?: boolean } = {}) {
  return {
    data: [],
    isLoading: overrides.isLoading ?? false,
  } as unknown as ReturnType<typeof useNotes>
}

// Type-safe mock factory for useNotebookChat hook
function createChatMock() {
  return {
    messages: [],
    isSending: false,
    tokenCount: 0,
    charCount: 0,
    sessions: [],
    currentSessionId: null,
    currentSession: null,
    pendingModelOverride: null,
    contextWindowUsage: null,
    chatMode: 'quick',
    cancelStreaming: vi.fn(),
  } as unknown as ReturnType<typeof useNotebookChat>
}

describe('ChatColumn', () => {
  const baseProps = {
    notebookId: 'test-notebook',
    contextSelections: {
      sources: {},
      notes: {}
    },
    sources: [],
  }

  beforeEach(() => {
    chatPanelMock.mockClear()
    vi.mocked(useModels).mockReturnValue({
      data: [{
        id: 'model:deepseek',
        name: 'deepseek-v4-pro',
        provider: 'deepseek',
        type: 'language',
        context_window_tokens: 1_000_000,
        context_window_source: 'builtin',
        created: '',
        updated: '',
      }],
    } as ReturnType<typeof useModels>)
    vi.mocked(useModelDefaults).mockReturnValue({
      data: { default_chat_model: 'model:deepseek' },
    } as ReturnType<typeof useModelDefaults>)
  })

  it('shows loading spinner when fetching data', () => {
    vi.mocked(useNotes).mockReturnValue(createNotesMock({ isLoading: true }))
    vi.mocked(useNotebookChat).mockReturnValue(createChatMock())
    vi.mocked(useNotebookGuide).mockReturnValue({ data: null, isLoading: false, isFetching: false } as never)
    vi.mocked(useRegenerateNotebookGuide).mockReturnValue({ mutate: vi.fn() } as never)

    render(<ChatColumn {...baseProps} sourcesLoading={true} />)

    // Should show loading spinner
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
  })

  it('renders chat panel when data is loaded', () => {
    vi.mocked(useNotes).mockReturnValue(createNotesMock({ isLoading: false }))
    vi.mocked(useNotebookChat).mockReturnValue(createChatMock())
    vi.mocked(useNotebookGuide).mockReturnValue({ data: null, isLoading: false, isFetching: false } as never)
    vi.mocked(useRegenerateNotebookGuide).mockReturnValue({ mutate: vi.fn() } as never)

    render(<ChatColumn {...baseProps} sourcesLoading={false} />)

    // Should show chat panel
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument()
    expect(chatPanelMock).toHaveBeenLastCalledWith(expect.objectContaining({
      contextWindowStats: expect.objectContaining({
        modelName: 'deepseek-v4-pro',
        contextWindowTokens: 1_000_000,
      }),
    }))
  })
})
