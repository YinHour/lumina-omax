import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ContextWindowMeter } from './ContextWindowMeter'

describe('ContextWindowMeter', () => {
  it('shows model, context usage, percentage, and progress for quick chat', () => {
    render(
      <ContextWindowMeter
        mode="quick"
        modelName="deepseek-v4-pro"
        usedTokens={93_400}
        contextWindowTokens={1_000_000}
      />
    )

    expect(screen.getByText('deepseek-v4-pro')).toBeInTheDocument()
    expect(screen.getByText(/93\.4K \/ 1M/)).toBeInTheDocument()
    expect(screen.getByText(/9%/)).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '9.34')
  })

  it('does not show a misleading fixed percentage for research mode', () => {
    render(
      <ContextWindowMeter
        mode="research"
        modelName="deepseek-v4-pro"
        usedTokens={93_400}
        contextWindowTokens={1_000_000}
      />
    )

    expect(screen.getByText('On-demand retrieval; context changes during each research step')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.queryByText(/9%/)).not.toBeInTheDocument()
  })
})
