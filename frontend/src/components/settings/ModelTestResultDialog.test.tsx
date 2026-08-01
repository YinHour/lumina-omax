import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ModelTestResultDialog } from './ModelTestResultDialog'

describe('ModelTestResultDialog', () => {
  it('shows context metadata saved by a successful model test', () => {
    render(
      <ModelTestResultDialog
        open
        onOpenChange={vi.fn()}
        modelName="vendor/model"
        result={{
          success: true,
          message: 'Response: Hi',
          context_window_tokens: 131_072,
          context_window_source: 'provider',
          context_window_saved: true,
        }}
      />
    )

    expect(screen.getByText('Context window (tokens):')).toBeInTheDocument()
    expect(screen.getByText('131,072')).toBeInTheDocument()
    expect(
      screen.getByText('Automatically detected and saved during this test.')
    ).toBeInTheDocument()
  })

  it('keeps a successful test explicit when the provider exposes no limit', () => {
    render(
      <ModelTestResultDialog
        open
        onOpenChange={vi.fn()}
        modelName="unknown/model"
        result={{ success: true, message: 'Response: Hi' }}
      />
    )

    expect(screen.getByText('Context limit not configured')).toBeInTheDocument()
  })
})
