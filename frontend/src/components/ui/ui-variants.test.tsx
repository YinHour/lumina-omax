import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Button, buttonVariants } from './button'
import { Card } from './card'
import { Checkbox } from './checkbox'
import { Input } from './input'
import { RadioGroup, RadioGroupItem } from './radio-group'
import { Select, SelectTrigger, SelectValue } from './select'
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

  it('preserves large button sizing for the link variant', () => {
    render(
      <Button variant="link" size="lg">
        Link
      </Button>
    )

    const link = screen.getByRole('button', { name: 'Link' })
    expect(link).toHaveClass('h-10', 'px-6')
    expect(link).not.toHaveClass('h-auto', 'p-0')
    expect(buttonVariants({ variant: 'link', size: 'lg' })).not.toMatch(
      /\b(?:h-auto|p-0)\b/
    )
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

  it('applies interactive card metadata and focus styling to a semantic child', () => {
    render(
      <Card asChild variant="interactive">
        <a href="/research">Research</a>
      </Card>
    )

    const link = screen.getByRole('link', { name: 'Research' })
    expect(link).toHaveAttribute('data-variant', 'interactive')
    expect(link).toHaveClass(
      'cursor-pointer',
      'focus-visible:ring-2',
      'focus-visible:ring-ring/35'
    )
  })

  it('keeps generated card metadata when caller data attributes conflict', () => {
    const conflictingMetadata = { 'data-variant': 'wrong' }

    render(
      <Card {...conflictingMetadata} variant="selected">
        Selected card
      </Card>
    )

    expect(screen.getByText('Selected card')).toHaveAttribute(
      'data-variant',
      'selected'
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

  it('styles select, checkbox, and radio controls consistently', () => {
    render(
      <>
        <Select>
          <SelectTrigger aria-label="Topic">
            <SelectValue placeholder="Choose a topic" />
          </SelectTrigger>
        </Select>
        <Checkbox aria-label="Include notes" />
        <RadioGroup aria-label="Format">
          <RadioGroupItem aria-label="Brief" value="brief" />
        </RadioGroup>
      </>
    )

    expect(screen.getByRole('combobox', { name: 'Topic' })).toHaveClass(
      'rounded-lg',
      'bg-card/70',
      'focus-visible:ring-2'
    )
    expect(
      screen.getByRole('checkbox', { name: 'Include notes' })
    ).toHaveClass('bg-card/70', 'focus-visible:ring-2')
    expect(screen.getByRole('radio', { name: 'Brief' })).toHaveClass(
      'bg-card/70',
      'focus-visible:ring-2'
    )
  })

  it('disables pointer interaction for text and select controls', () => {
    render(
      <>
        <Input aria-label="Disabled title" disabled />
        <Textarea aria-label="Disabled description" disabled />
        <Select disabled>
          <SelectTrigger aria-label="Disabled topic">
            <SelectValue placeholder="Choose a topic" />
          </SelectTrigger>
        </Select>
      </>
    )

    expect(screen.getByRole('textbox', { name: 'Disabled title' })).toHaveClass(
      'disabled:pointer-events-none'
    )
    expect(
      screen.getByRole('textbox', { name: 'Disabled description' })
    ).toHaveClass('disabled:pointer-events-none')
    expect(
      screen.getByRole('combobox', { name: 'Disabled topic' })
    ).toHaveClass('disabled:pointer-events-none')
  })
})
