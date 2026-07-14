import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ContextWindowMeter } from './ContextWindowMeter'

describe('ContextWindowMeter', () => {
  it('does not render a separate meter for quick chat', () => {
    render(
      <ContextWindowMeter
        mode="quick"
        modelName="deepseek-v4-pro"
      />
    )

    expect(screen.queryByTestId('context-window-meter')).not.toBeInTheDocument()
  })

  it('does not show a misleading fixed percentage for research mode', () => {
    render(
      <ContextWindowMeter
        mode="research"
        modelName="deepseek-v4-pro"
      />
    )

    expect(screen.getByText('On-demand retrieval; context changes during each research step')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.queryByText(/9%/)).not.toBeInTheDocument()
  })
})
