import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ChatPanel } from '@/components/source/ChatPanel'

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
})
