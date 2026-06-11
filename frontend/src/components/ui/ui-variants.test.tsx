import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Button } from './button'
import { Card } from './card'
import { Input } from './input'
import { Textarea } from './textarea'

describe('core UI variants', () => {
  it('uses a rounded button with restrained transitions', () => {
    render(<Button>Continue</Button>)

    const button = screen.getByRole('button', { name: 'Continue' })
    expect(button).toHaveClass('rounded-lg')
    expect(button).toHaveClass(
      'transition-[color,background-color,border-color,box-shadow,opacity]'
    )
    expect(button).toHaveClass('duration-200')
    expect(button).not.toHaveClass('transition-all')
  })

  it.each(['interactive', 'selected', 'insight'] as const)(
    'exposes the %s card variant',
    (variant) => {
      render(<Card variant={variant}>Card content</Card>)

      expect(screen.getByText('Card content')).toHaveAttribute(
        'data-variant',
        variant
      )
    }
  )

  it('defaults the card data variant', () => {
    render(<Card>Default card</Card>)

    expect(screen.getByText('Default card')).toHaveAttribute(
      'data-variant',
      'default'
    )
  })

  it('uses warm rounded surfaces for text controls', () => {
    render(
      <>
        <Input aria-label="Title" />
        <Textarea aria-label="Description" />
      </>
    )

    expect(screen.getByRole('textbox', { name: 'Title' })).toHaveClass(
      'rounded-lg',
      'bg-card/70'
    )
    expect(screen.getByRole('textbox', { name: 'Description' })).toHaveClass(
      'rounded-lg',
      'bg-card/70'
    )
  })
})
