import { Alert as AlertIcon, Check, Copy, Info, Spinner } from './Icons'
import { useState } from 'react'

/** Panel with an optional title and subtitle. */
export function Card({ title, subtitle, action, children, className = '', pad = true }) {
  return (
    <section className={`card ${pad ? 'card-pad' : ''} ${className}`}>
      {(title || action) && (
        <header className={`flex items-start justify-between gap-4 ${children ? 'mb-4' : ''}`}>
          <div>
            {title && <h2 className="panel-title">{title}</h2>}
            {subtitle && <p className="panel-sub">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

/**
 * Status badge. Colour is always accompanied by an icon and a text label, so
 * the state survives colour-blindness, greyscale printing and forced colours.
 */
export function Badge({ tone = 'neutral', icon: Icon, children }) {
  const tones = {
    neutral: 'badge-neutral',
    good: 'text-status-good',
    warn: 'text-status-warn',
    critical: 'text-status-critical',
  }
  const backgrounds = {
    neutral: undefined,
    good: 'var(--status-good-bg)',
    warn: 'var(--status-warn-bg)',
    critical: 'var(--status-crit-bg)',
  }
  return (
    <span className={`badge ${tones[tone]}`} style={{ background: backgrounds[tone] }}>
      {Icon && <Icon size={13} />}
      {children}
    </span>
  )
}

/** Inline notice. `tone` selects the icon as well as the colour. */
export function Notice({ tone = 'info', title, children, className = '' }) {
  const config = {
    info: { color: 'var(--accent)', bg: 'var(--accent-soft)', Icon: Info },
    warn: { color: 'var(--status-warn)', bg: 'var(--status-warn-bg)', Icon: AlertIcon },
    critical: { color: 'var(--status-critical)', bg: 'var(--status-crit-bg)', Icon: AlertIcon },
  }[tone]

  return (
    <div
      className={`flex gap-3 rounded-xl p-4 ${className}`}
      style={{ background: config.bg, border: `1px solid ${config.color}33` }}
      role={tone === 'info' ? undefined : 'alert'}
    >
      <span className="mt-px shrink-0" style={{ color: config.color }}>
        <config.Icon size={17} />
      </span>
      <div className="min-w-0 text-[0.8125rem] leading-relaxed">
        {title && (
          <p className="font-semibold" style={{ color: config.color }}>{title}</p>
        )}
        <div className={title ? 'mt-1 text-ink-secondary' : 'text-ink-secondary'}>{children}</div>
      </div>
    </div>
  )
}

/** Compact labelled metric. */
export function Stat({ label, value, hint, tone }) {
  return (
    <div className="rounded-lg px-4 py-3" style={{ background: 'var(--surface-2)' }}>
      <p className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-muted">
        {label}
      </p>
      <p className="tnum mt-1 text-xl font-bold tracking-tight"
         style={{ color: tone || 'var(--text-primary)' }}>
        {value}
      </p>
      {hint && <p className="mt-0.5 text-[0.75rem] text-ink-muted">{hint}</p>}
    </div>
  )
}

/** Definition row used in the file-details panels. */
export function Field({ label, children, mono = false, wide = false }) {
  return (
    <div className={wide ? 'sm:col-span-2' : ''}>
      <dt className="text-[0.75rem] font-medium uppercase tracking-wide text-ink-muted">
        {label}
      </dt>
      <dd className={`mt-1 text-[0.875rem] text-ink-primary ${mono ? 'mono break-all text-[0.75rem]' : ''}`}>
        {children}
      </dd>
    </div>
  )
}

/** Copy-to-clipboard control for hashes and references. */
export function CopyButton({ value, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable (insecure origin) — the value is still selectable */
    }
  }

  return (
    <button onClick={copy} className="btn-ghost px-2 py-1 text-[0.75rem]"
            aria-label={copied ? 'Copied' : label}>
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? 'Copied' : label}
    </button>
  )
}

/** Loading placeholder that mirrors the shape of the content it replaces. */
export function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`} />
}

export function LoadingState({ title, detail }) {
  return (
    <div className="flex flex-col items-center py-14 text-center">
      <span className="text-accent"><Spinner size={26} /></span>
      <p className="mt-4 font-semibold text-ink-primary">{title}</p>
      {detail && <p className="mt-1 max-w-sm text-[0.8125rem] text-ink-muted">{detail}</p>}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, detail, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      {Icon && (
        <span className="mb-4 grid h-12 w-12 place-items-center rounded-xl text-ink-muted"
              style={{ background: 'var(--surface-2)' }}>
          <Icon size={22} />
        </span>
      )}
      <p className="font-semibold text-ink-primary">{title}</p>
      {detail && <p className="mt-1 max-w-sm text-[0.8125rem] text-ink-muted">{detail}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/** Horizontal probability meter with the decision bands drawn in. */
export function ProbabilityMeter({ value, threshold = 0.5, band = 0.15 }) {
  const pct = Math.max(0, Math.min(1, value ?? 0)) * 100
  const low = (threshold - band) * 100
  const high = (threshold + band) * 100

  return (
    <div>
      <div className="relative h-9 overflow-hidden rounded-lg"
           style={{ background: 'var(--surface-2)' }}>
        <div className="absolute inset-y-0 left-0" style={{ width: `${low}%`,
             background: 'var(--status-good-bg)' }} />
        <div className="absolute inset-y-0" style={{ left: `${low}%`, width: `${high - low}%`,
             background: 'var(--status-warn-bg)' }} />
        <div className="absolute inset-y-0" style={{ left: `${high}%`, width: `${100 - high}%`,
             background: 'var(--status-crit-bg)' }} />
        <div className="absolute inset-y-0 w-[3px] rounded-full"
             style={{ left: `calc(${pct}% - 1.5px)`, background: 'var(--text-primary)' }}
             role="img" aria-label={`Probability of manipulation ${pct.toFixed(1)} percent`} />
      </div>
      <div className="mt-1.5 flex justify-between text-[0.6875rem] font-medium text-ink-muted">
        <span>0% · authentic</span>
        <span>{(threshold * 100).toFixed(0)}% · undecided</span>
        <span>100% · manipulated</span>
      </div>
    </div>
  )
}
