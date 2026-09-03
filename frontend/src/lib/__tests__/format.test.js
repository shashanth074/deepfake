import { describe, expect, it } from 'vitest'
import { formatBytes, formatDuration, percent, verdictMeta } from '../format'

describe('verdictMeta', () => {
  it('pairs every verdict with an icon and a label, never colour alone', () => {
    for (const verdict of ['likely_authentic', 'likely_manipulated', 'inconclusive']) {
      const meta = verdictMeta(verdict)
      expect(meta.label).toBeTruthy()
      expect(meta.icon).toBeTypeOf('function')
      expect(meta.color).toBeTruthy()
    }
  })

  it('falls back safely for an unknown verdict', () => {
    expect(verdictMeta(undefined).label).toBe('Not analysed')
    expect(verdictMeta('nonsense').icon).toBeTypeOf('function')
  })
})

describe('formatBytes', () => {
  it.each([
    [0, '0 B'],
    [512, '512 B'],
    [2048, '2.0 KB'],
    [5 * 1024 * 1024, '5.00 MB'],
  ])('formats %i as %s', (input, expected) => {
    expect(formatBytes(input)).toBe(expected)
  })

  it('renders a dash rather than "undefined" when the size is missing', () => {
    expect(formatBytes(undefined)).toBe('—')
    expect(formatBytes(null)).toBe('—')
  })
})

describe('percent', () => {
  it('formats a probability', () => {
    expect(percent(0.8734)).toBe('87.3%')
  })

  it('distinguishes a genuine zero from a missing value', () => {
    expect(percent(0)).toBe('0.0%')
    expect(percent(null)).toBe('—')
  })
})

describe('formatDuration', () => {
  it('uses milliseconds below a second and seconds above', () => {
    expect(formatDuration(250)).toBe('250 ms')
    expect(formatDuration(4210)).toBe('4.2 s')
  })
})
