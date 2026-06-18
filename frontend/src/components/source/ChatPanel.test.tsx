import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ChatPanel } from '@/components/source/ChatPanel'

vi.mock('@/components/source/MessageActions', () => ({
  MessageActions: () => <div data-testid="message-actions" />,
}))

// useTranslation mocked globally in setup.ts returns enUS locale keys

describe('ChatPanel stop button', () => {
  beforeEach(() => {
    localStorage.clear()
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
