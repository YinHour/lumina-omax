import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StreamingResponse } from './StreamingResponse'

const { openModalMock } = vi.hoisted(() => ({
  openModalMock: vi.fn(),
}))

vi.mock('@/lib/hooks/use-modal-manager', () => ({
  useModalManager: () => ({
    openModal: openModalMock,
  }),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('StreamingResponse', () => {
  beforeEach(() => {
    openModalMock.mockClear()
  })

  it('renders a visible Ask progress panel while streaming', () => {
    render(
      <StreamingResponse
        isStreaming={true}
        strategy={null}
        answers={[]}
        finalAnswer={null}
        progress={{
          stage: 'searching',
          elapsedSeconds: 8,
          terminal: null,
        }}
      />
    )

    expect(screen.getByText('Question received, working on it')).toBeInTheDocument()
    expect(screen.getByText('8s elapsed')).toBeInTheDocument()
    expect(screen.getByText('Received')).toBeInTheDocument()
    expect(screen.getByText('Planning')).toBeInTheDocument()
    expect(screen.getByText('Searching')).toBeInTheDocument()
    expect(screen.getByText('Writing')).toBeInTheDocument()
  })

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

  it('renders LaTeX and raw HTML tables in the final answer', () => {
    const { container } = render(
      <StreamingResponse
        isStreaming={false}
        strategy={null}
        answers={[]}
        finalAnswer={'Inline $C_3A$\n\n$$w_d = \\frac{m_2-m_0}{m_1-m_0}$$\n\n<table><tbody><tr><td>Rendered cell</td></tr></tbody></table>'}
      />
    )

    expect(container.querySelectorAll('.katex')).toHaveLength(2)
    expect(container.querySelector('.katex-display')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Rendered cell' })).toBeInTheDocument()
  })

  it('opens insight aliases in the insight preview', () => {
    render(
      <StreamingResponse
        isStreaming={false}
        strategy={null}
        answers={[]}
        finalAnswer={'See [insight:ide0gvve6vdoqm6tvt35].'}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '[insight:ide0gvve6vdoqm6tvt35]' }))
    expect(openModalMock).toHaveBeenCalledWith('insight', 'ide0gvve6vdoqm6tvt35')
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
