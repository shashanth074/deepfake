import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge, Notice, ProbabilityMeter, Stat } from '../ui'
import { ShieldCheck } from '../ui/Icons'

describe('Badge', () => {
  it('renders its label as text, so status is never colour-only', () => {
    render(<Badge tone="critical" icon={ShieldCheck}>Manipulated</Badge>)
    expect(screen.getByText('Manipulated')).toBeInTheDocument()
  })
})

describe('Notice', () => {
  it('marks non-informational notices as alerts for screen readers', () => {
    render(<Notice tone="critical" title="Problem">Something failed</Notice>)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Problem')).toBeInTheDocument()
  })

  it('does not raise an alert for ordinary information', () => {
    render(<Notice tone="info">Just so you know</Notice>)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('ProbabilityMeter', () => {
  it('exposes the score to assistive technology', () => {
    render(<ProbabilityMeter value={0.873} />)
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      'Probability of manipulation 87.3 percent',
    )
  })

  it('clamps an out-of-range value instead of overflowing the track', () => {
    render(<ProbabilityMeter value={1.9} />)
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      'Probability of manipulation 100.0 percent',
    )
  })
})

describe('Stat', () => {
  it('shows its label and value', () => {
    render(<Stat label="Decision confidence" value="74.0%" hint="from the midpoint" />)
    expect(screen.getByText('Decision confidence')).toBeInTheDocument()
    expect(screen.getByText('74.0%')).toBeInTheDocument()
  })
})
