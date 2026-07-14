import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ContextIndicator } from './ContextIndicator'

describe('ContextIndicator', () => {
  it('shows source modes, selected tokens, and model context usage in one summary row', () => {
    render(
      <ContextIndicator
        sourcesInsights={2}
        sourcesFull={17}
        notesCount={3}
        tokenCount={66_000}
        usedTokens={112_000}
        contextWindowTokens={1_000_000}
      />
    )

    const summary = screen.getByTestId('context-summary')
    expect(summary).toHaveClass('grid')
    expect(screen.getByTestId('context-source-counts')).toHaveClass('justify-self-start')
    expect(screen.getByTestId('context-source-counts')).toHaveTextContent('Context:2173')
    expect(screen.getByTestId('context-source-tokens')).toHaveClass('justify-self-center')
    expect(screen.getByTestId('context-source-tokens')).toHaveTextContent('66.0K tokens')
    expect(screen.getByTestId('context-window-usage')).toHaveClass('justify-self-end')
    expect(screen.getByTestId('context-window-usage')).toHaveTextContent('≈112K / 1M11%')
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '11.2')
  })

  it('keeps the row stable before the first question', () => {
    render(
      <ContextIndicator
        sourcesInsights={0}
        sourcesFull={0}
        notesCount={0}
        tokenCount={0}
        contextWindowTokens={1_000_000}
      />
    )

    expect(screen.getByTestId('context-source-counts')).toHaveTextContent('Context:0')
    expect(screen.getByTestId('context-source-tokens')).toHaveTextContent('0 tokens')
    expect(screen.getByTestId('context-window-usage')).toHaveTextContent('-- / 1M')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
})
