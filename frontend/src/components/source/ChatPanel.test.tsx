import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { ChatPanel } from '@/components/source/ChatPanel'

const { openModalMock } = vi.hoisted(() => ({
  openModalMock: vi.fn(),
}))

vi.mock('@/lib/hooks/use-modal-manager', () => ({
  useModalManager: () => ({ openModal: openModalMock }),
}))

vi.mock('@/components/source/MessageActions', () => ({
  MessageActions: () => <div data-testid="message-actions" />,
}))

// useTranslation mocked globally in setup.ts returns enUS locale keys

describe('ChatPanel stop button', () => {
  beforeEach(() => {
    localStorage.clear()
    openModalMock.mockClear()
  })

  const baseProps = {
    messages: [],
    isStreaming: false,
    contextIndicators: null,
    onSendMessage: vi.fn(),
  }

  it('renders Send button when not streaming', () => {
    render(<ChatPanel {...baseProps} />)
    // The send button has the sendPlaceholder as aria-label
    const sendBtn = screen.getByRole('button', { name: /ask anything about your sources/i })
    expect(sendBtn).toBeInTheDocument()
  })

  it('renders notebook modes as tabs with mode-specific bottom controls', () => {
    const onModeChange = vi.fn()
    const onCrossChange = vi.fn()
    const onStartNewSession = vi.fn()
    const onSelectSession = vi.fn()
    const { rerender } = render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        chatMode="quick"
        onChatModeChange={onModeChange}
        onAllowCrossNotebookDiscoveryChange={onCrossChange}
        onStartNewSession={onStartNewSession}
        onSelectSession={onSelectSession}
      />
    )

    expect(screen.getByRole('tab', { name: 'Quick Chat' })).toHaveAttribute('data-state', 'active')
    expect(screen.getByRole('tab', { name: 'Quick Chat' })).toHaveClass('whitespace-nowrap')
    expect(screen.getByRole('tab', { name: 'Research Agent' })).toHaveAttribute('data-state', 'inactive')
    expect(screen.getByRole('tab', { name: 'Research Agent' })).toHaveClass('whitespace-nowrap')
    const optionsRow = screen.getByTestId('chat-options-row')
    expect(within(optionsRow).getAllByRole('checkbox')).toHaveLength(1)
    expect(within(optionsRow).getByRole('checkbox', { name: 'Web Search' })).not.toBeChecked()

    const researchTab = screen.getByRole('tab', { name: 'Research Agent' })
    fireEvent.mouseDown(researchTab, { button: 0 })
    fireEvent.click(researchTab)
    expect(onModeChange).toHaveBeenCalledWith('research')

    rerender(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        chatMode="research"
        onChatModeChange={onModeChange}
        onAllowCrossNotebookDiscoveryChange={onCrossChange}
        onStartNewSession={onStartNewSession}
        onSelectSession={onSelectSession}
      />
    )
    expect(within(optionsRow).getAllByRole('checkbox')).toHaveLength(2)
    expect(within(optionsRow).getByRole('checkbox', { name: 'Cross-notebook discovery' })).not.toBeChecked()
    fireEvent.click(within(optionsRow).getByText('Cross-notebook discovery'))
    expect(onCrossChange).toHaveBeenCalledWith(true)
  })

  it('toggles web search by clicking its text label', () => {
    render(<ChatPanel {...baseProps} />)

    const webSearch = screen.getByRole('checkbox', { name: 'Web Search' })
    expect(webSearch).not.toBeChecked()
    fireEvent.click(screen.getByText('Web Search'))
    expect(webSearch).toBeChecked()
    fireEvent.click(screen.getByText('Web Search'))
    expect(webSearch).not.toBeChecked()
  })

  it('does not show Research Agent controls in source chat', () => {
    render(<ChatPanel {...baseProps} contextType="source" />)
    expect(screen.queryByRole('tab', { name: 'Research Agent' })).not.toBeInTheDocument()
  })

  it('keeps independent input drafts for Quick and Research tabs', () => {
    const sharedProps = {
      ...baseProps,
      contextType: 'notebook' as const,
      onChatModeChange: vi.fn(),
      onStartNewSession: vi.fn(),
      onSelectSession: vi.fn(),
    }
    const { rerender } = render(<ChatPanel {...sharedProps} chatMode="quick" />)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'quick draft' } })
    rerender(<ChatPanel {...sharedProps} chatMode="research" />)
    expect(screen.getByRole('textbox')).toHaveValue('')
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'research draft' } })

    rerender(<ChatPanel {...sharedProps} chatMode="quick" />)
    expect(screen.getByRole('textbox')).toHaveValue('quick draft')
  })

  it('shows save state and exposes an explicit new-conversation action', () => {
    const onStartNewSession = vi.fn()
    render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        onChatModeChange={vi.fn()}
        onStartNewSession={onStartNewSession}
        onSelectSession={vi.fn()}
        saveStatus="saved"
      />
    )

    expect(screen.getByTestId('chat-save-status')).toHaveTextContent('Saved')
    fireEvent.click(screen.getByRole('button', { name: 'New conversation' }))
    expect(onStartNewSession).toHaveBeenCalledTimes(1)
  })

  it('offers loading earlier messages for paginated notebook transcripts', () => {
    const onLoadEarlierMessages = vi.fn().mockResolvedValue(undefined)
    render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        onChatModeChange={vi.fn()}
        onStartNewSession={vi.fn()}
        onSelectSession={vi.fn()}
        hasMoreMessages
        onLoadEarlierMessages={onLoadEarlierMessages}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Load earlier messages' }))
    expect(onLoadEarlierMessages).toHaveBeenCalledOnce()
  })

  it('does not render model thinking tags or reasoning content', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ChatPanel
        {...baseProps}
        messages={[{
          id: 'ai-thinking',
          type: 'ai',
          content: '<think>private chain of thought</think>Public answer',
        }]}
      />
    )

    expect(screen.getByText('Public answer')).toBeInTheDocument()
    expect(screen.queryByText('private chain of thought')).not.toBeInTheDocument()
    expect(
      consoleError.mock.calls.some(call => String(call[0]).includes('unrecognized')),
    ).toBe(false)
    consoleError.mockRestore()
  })

  it('renders Stop button when streaming with onCancelStreaming', () => {
    const onCancel = vi.fn()
    render(
      <ChatPanel
        {...baseProps}
        isStreaming={true}
        onCancelStreaming={onCancel}
      />
    )
    expect(screen.getByRole('button', { name: /stop generating/i })).toBeInTheDocument()
  })

  it('calls onCancelStreaming when stop button is clicked', () => {
    const onCancel = vi.fn()
    render(
      <ChatPanel
        {...baseProps}
        isStreaming={true}
        onCancelStreaming={onCancel}
      />
    )
    const stopBtn = screen.getByRole('button', { name: /stop generating/i })
    fireEvent.click(stopBtn)
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('shows spinner (not stop) when streaming but no onCancelStreaming provided', () => {
    render(<ChatPanel {...baseProps} isStreaming={true} />)
    // The button shows a Loader2 spinner, no stop text
    expect(screen.queryByRole('button', { name: /stop generating/i })).not.toBeInTheDocument()
  })

  it('disables input and web search toggle while streaming', () => {
    render(<ChatPanel {...baseProps} isStreaming={true} />)
    // Input is disabled
    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeDisabled()
  })

  it('renders notebook guide and sends clicked guide question immediately', () => {
    const onSendMessage = vi.fn()
    render(
      <ChatPanel
        {...baseProps}
        title="Research notebook"
        contextType="notebook"
        onSendMessage={onSendMessage}
        notebookGuide={{
          notebook_id: 'notebook:1',
          source_count: 1,
          generated_at: '2026-06-11T00:00:00Z',
          summary: 'This notebook summarizes a source about oilfield chemistry.',
          questions: ['What mechanism should we compare?', 'Which risks need validation?', 'What experiment comes next?'],
          status: 'ready',
        }}
      />
    )

    expect(screen.getByText('This notebook summarizes a source about oilfield chemistry.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'What mechanism should we compare?' }))
    expect(onSendMessage).toHaveBeenCalledWith('What mechanism should we compare?', undefined, false)
  })

  it('keeps the notebook guide visible after conversation starts', () => {
    render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        messages={[
          {
            id: 'human-1',
            type: 'human',
            content: 'What does this source say?',
          },
        ]}
        notebookGuide={{
          notebook_id: 'notebook:1',
          source_count: 1,
          generated_at: '2026-06-11T00:00:00Z',
          summary: 'Persistent guide summary.',
          questions: ['What mechanism should we compare?', 'Which risks need validation?', 'What experiment comes next?'],
          status: 'ready',
        }}
      />
    )

    expect(screen.getByText('Persistent guide summary.')).toBeInTheDocument()
  })

  it('shows guide generation feedback while guide is loading', () => {
    render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        isGuideLoading={true}
      />
    )

    expect(screen.getByText('Generating notebook guide...')).toBeInTheDocument()
    expect(screen.getByText('Reading selected sources')).toBeInTheDocument()
  })

  it('renders follow-up questions under AI messages and sends clicked question immediately', () => {
    const onSendMessage = vi.fn()
    render(
      <ChatPanel
        {...baseProps}
        onSendMessage={onSendMessage}
        messages={[
          {
            id: 'ai-1',
            type: 'ai',
            content: 'The answer discusses mechanism validation.',
          },
        ]}
        suggestedQuestionsByMessageId={{
          'ai-1': ['How should we validate this mechanism?', 'What evidence is missing?', 'Which source should we inspect?'],
        }}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'How should we validate this mechanism?' }))
    expect(onSendMessage).toHaveBeenCalledWith('How should we validate this mechanism?', undefined, false)
  })

  it('keeps the chat scroll content constrained to the viewport wrapper', () => {
    const { container } = render(
      <ChatPanel
        {...baseProps}
        messages={[
          {
            id: 'ai-1',
            type: 'ai',
            content: [
              '| source | very long extracted value |',
              '| --- | --- |',
              '| pipeline_img.img | source:mgajv5fjc673z9lza17l source:selxd23o70g3cw52pt3n source:z3wu0ugit553ndlhwv3s |',
            ].join('\n'),
          },
        ]}
      />
    )

    expect(container.querySelector('[data-slot="scroll-area-viewport"]')).toHaveClass('[&>div]:!block')
  })

  it('turns escaped inline workspace citations into source links', () => {
    render(
      <ChatPanel
        {...baseProps}
        messages={[
          {
            id: 'ai-reference',
            type: 'ai',
            content: 'Evidence comes from \\[1\\]\\(#ref-source-abc123\\) and ``[2](#ref-source-def456)``.',
          },
        ]}
      />
    )

    expect(screen.queryByText('[1](#ref-source-abc123)')).not.toBeInTheDocument()
    expect(screen.queryByText('[2](#ref-source-def456)')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '1' }))
    expect(openModalMock).toHaveBeenCalledWith('source', 'abc123')
    fireEvent.click(screen.getByRole('button', { name: '2' }))
    expect(openModalMock).toHaveBeenCalledWith('source', 'def456')
  })

  it('renders inline and block LaTeX in AI messages', () => {
    const { container } = render(
      <ChatPanel
        {...baseProps}
        messages={[{
          id: 'ai-math',
          type: 'ai',
          content: '活性最高的铝酸三钙($C_3A$)\n\n$$w_d = \\frac{m_2 - m_0}{m_1 - m_0} \\times 100\\%$$',
        }]}
      />
    )

    expect(container.querySelectorAll('.katex')).toHaveLength(2)
    expect(container.querySelector('.katex-display')).toBeInTheDocument()
  })

  it('opens insight aliases in the insight preview', () => {
    render(
      <ChatPanel
        {...baseProps}
        messages={[{
          id: 'ai-insight-reference',
          type: 'ai',
          content: 'See [insight:ide0gvve6vdoqm6tvt35].',
        }]}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '1' }))
    expect(openModalMock).toHaveBeenCalledWith('insight', 'ide0gvve6vdoqm6tvt35')
  })

  it('disables suggested questions while streaming', () => {
    render(
      <ChatPanel
        {...baseProps}
        isStreaming={true}
        messages={[
          {
            id: 'ai-1',
            type: 'ai',
            content: 'The answer discusses mechanism validation.',
          },
        ]}
        suggestedQuestionsByMessageId={{
          'ai-1': ['How should we validate this mechanism?'],
        }}
      />
    )

    expect(screen.getByRole('button', { name: 'How should we validate this mechanism?' })).toBeDisabled()
  })

  it('shows a lightweight activity status below the latest user message while waiting', () => {
    render(
      <ChatPanel
        {...baseProps}
        isStreaming={true}
        messages={[
          {
            id: 'human-1',
            type: 'human',
            content: 'How does this material behave under heat?',
          },
        ]}
        activityStatus="gettingContext"
      />
    )

    expect(screen.getByText('Getting the context...')).toBeInTheDocument()
  })

  it('shows live notebook activity directly below the triggering question', () => {
    render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        isStreaming={true}
        messages={[{
          id: 'human-activity',
          type: 'human',
          content: 'Compare the catalyst evidence.',
        }]}
        activityMessageId="human-activity"
        activityTotalElapsedSeconds={4}
        activitySteps={[
          { stage: 'received', status: 'complete' },
          { stage: 'searching_notebook', status: 'active' },
        ]}
      />
    )

    const feed = screen.getByTestId('chat-activity-feed')
    expect(screen.getByText('Compare the catalyst evidence.').parentElement?.parentElement?.parentElement?.nextElementSibling).toContainElement(feed)
    expect(within(feed).getByText('Question received')).toBeInTheDocument()
    expect(within(feed).getByText('Searching this notebook')).toBeInTheDocument()
    expect(within(feed).getByText('Working (4s)')).toBeInTheDocument()
  })

  it('collapses completed notebook activity and lets the user expand it', () => {
    render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        messages={[{
          id: 'human-complete',
          type: 'human',
          content: 'Summarize the evidence.',
        }]}
        activityMessageId="human-complete"
        activityTotalElapsedSeconds={12}
        activityTerminal="complete"
        activitySteps={[
          { stage: 'received', status: 'complete' },
          { stage: 'model_streaming', status: 'complete' },
        ]}
      />
    )

    expect(screen.getByText('Completed 2 steps in 12s')).toBeInTheDocument()
    expect(screen.queryByText('Question received')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Expand activity' }))
    expect(screen.getByText('Question received')).toBeInTheDocument()
    expect(screen.getByText('Writing the answer')).toBeInTheDocument()
  })

  it('marks only the active step as failed in an error activity feed', () => {
    render(
      <ChatPanel
        {...baseProps}
        contextType="notebook"
        messages={[{
          id: 'human-error',
          type: 'human',
          content: 'Inspect the evidence.',
        }]}
        activityMessageId="human-error"
        activityTerminal="error"
        activitySteps={[
          { stage: 'received', status: 'complete' },
          { stage: 'reading_evidence', status: 'error' },
        ]}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Expand activity' }))
    expect(screen.getByText('Question received').closest('li')).toHaveAttribute('data-status', 'complete')
    expect(screen.getByText('Reading relevant evidence').closest('li')).toHaveAttribute('data-status', 'error')
  })

  it('copies a sent human question back into the input for editing', () => {
    render(
      <ChatPanel
        {...baseProps}
        messages={[
          {
            id: 'human-1',
            type: 'human',
            content: 'How does this material behave under heat?',
          },
        ]}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /edit and ask again/i }))

    expect(screen.getByRole('textbox')).toHaveValue('How does this material behave under heat?')
  })

  it('hides the activity status after an AI response has started', () => {
    render(
      <ChatPanel
        {...baseProps}
        isStreaming={true}
        messages={[
          {
            id: 'human-1',
            type: 'human',
            content: 'How does this material behave under heat?',
          },
          {
            id: 'ai-1',
            type: 'ai',
            content: 'The response has started.',
          },
        ]}
        activityStatus="gettingContext"
      />
    )

    expect(screen.queryByText('Getting the context...')).not.toBeInTheDocument()
  })
})
