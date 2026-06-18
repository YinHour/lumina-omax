import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { StreamingResponse } from './StreamingResponse'

vi.mock('@/lib/hooks/use-modal-manager', () => ({
  useModalManager: () => ({
    openModal: vi.fn(),
  }),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('StreamingResponse', () => {
  it('renders the final answer as formatted markdown', () => {
    render(
      <StreamingResponse
        isStreaming={false}
        strategy={null}
        answers={[]}
        finalAnswer={'## Summary\n\n- First point\n- Second point\n\n**Done**'}
      />
    )

    expect(screen.getByRole('heading', { name: 'Summary' })).toBeInTheDocument()
    expect(screen.getByText('First point')).toBeInTheDocument()
    expect(screen.getByText('Second point')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('renders individual answers as markdown too', () => {
    render(
      <StreamingResponse
        isStreaming={false}
        strategy={null}
        answers={['### Candidate\n\n1. Step one\n2. Step two']}
        finalAnswer={null}
      />
    )

    expect(screen.getByRole('heading', { name: 'Candidate' })).toBeInTheDocument()
    expect(screen.getByText('Step one')).toBeInTheDocument()
    expect(screen.getByText('Step two')).toBeInTheDocument()
  })

  it('lets long answers expand with the page instead of using a nested scroll box', () => {
    const { container } = render(
      <StreamingResponse
        isStreaming={false}
        strategy={null}
        answers={[]}
        finalAnswer={'A long answer'}
      />
    )

    const region = container.querySelector('[role="region"]')

    expect(region).toHaveClass('min-w-0')
    expect(region).not.toHaveClass('max-h-[60vh]')
    expect(region).not.toHaveClass('overflow-y-auto')
  })

  it('renders Ask coverage metadata when provided', () => {
    render(
      <StreamingResponse
        isStreaming={false}
        strategy={null}
        answers={[]}
        finalAnswer={'Answer'}
        coverage={{
          total_sources: 32,
          embedded_sources: 31,
          retrieved_sources: 10,
          retrieved_source_ids: ['source:a', 'source:b'],
        }}
      />
    )

    expect(screen.getByText('32')).toBeInTheDocument()
    expect(screen.getByText('31')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
  })
})
