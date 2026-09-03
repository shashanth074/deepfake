import { ShieldAlert, ShieldCheck, ShieldQuestion } from '../components/ui/Icons'

/**
 * Verdict presentation.
 *
 * Every verdict carries an icon and a label alongside its colour — status is
 * never signalled by colour alone.
 */
export const VERDICT = {
  likely_authentic: {
    label: 'Likely authentic',
    short: 'Authentic',
    tone: 'good',
    color: 'var(--status-good)',
    bg: 'var(--status-good-bg)',
    icon: ShieldCheck,
    blurb: 'No strong indicators of manipulation were found in this file.',
  },
  likely_manipulated: {
    label: 'Likely manipulated',
    short: 'Manipulated',
    tone: 'critical',
    color: 'var(--status-critical)',
    bg: 'var(--status-crit-bg)',
    icon: ShieldAlert,
    blurb: 'Signals consistent with AI generation or manipulation were detected.',
  },
  inconclusive: {
    label: 'Inconclusive',
    short: 'Inconclusive',
    tone: 'warn',
    color: 'var(--status-warn)',
    bg: 'var(--status-warn-bg)',
    icon: ShieldQuestion,
    blurb: 'The score sits too close to the decision boundary to call either way.',
  },
}

export function verdictMeta(verdict) {
  return (
    VERDICT[verdict] || {
      label: 'Not analysed',
      short: 'Pending',
      tone: 'neutral',
      color: 'var(--text-muted)',
      bg: 'var(--surface-2)',
      icon: ShieldQuestion,
      blurb: '',
    }
  )
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export function formatDuration(ms) {
  if (!ms && ms !== 0) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

export function percent(value, digits = 1) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}
