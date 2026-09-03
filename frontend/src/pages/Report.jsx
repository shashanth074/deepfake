import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, getToken } from '../lib/api'
import { formatDate, percent, verdictMeta } from '../lib/format'
import { Badge, Card, CopyButton, Field, LoadingState, Notice } from '../components/ui'
import { ArrowRight, Check, Download, Hash, Spinner } from '../components/ui/Icons'

const SECTIONS = [
  'Header — report reference, case reference, generation timestamp',
  'Submitted file details — filename, type, size, SHA-256, upload time',
  'Analysis summary — model, version, verdict, confidence',
  'Detailed findings — heatmap or spectrogram, per-frame or per-window chart',
  'Methodology — written in plain language for a non-technical reader',
  'Limitations and disclaimer',
  'Report integrity — hashes and how to verify them',
]

export default function Report() {
  const { jobId } = useParams()
  const [result, setResult] = useState(null)
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [downloaded, setDownloaded] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([api.jobResult(jobId), api.createReport(jobId)])
      .then(([jobResult, generated]) => {
        if (!active) return
        setResult(jobResult)
        setReport(generated)
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setBusy(false))
    return () => { active = false }
  }, [jobId])

  /** Fetch rather than link: the endpoint needs the Authorization header. */
  async function download() {
    setDownloading(true)
    try {
      const response = await fetch(api.reportUrl(jobId), {
        headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
      })
      if (!response.ok) throw new Error(`Download failed (${response.status})`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${report?.report_reference || 'forensic-report'}.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      setDownloaded(true)
      setTimeout(() => setDownloaded(false), 2500)
    } catch (err) {
      setError(err.message)
    } finally {
      setDownloading(false)
    }
  }

  if (busy) {
    return (
      <div className="mx-auto max-w-2xl animate-in">
        <Card>
          <LoadingState title="Generating your report…"
                        detail="Rendering the evidence charts and computing the integrity hash." />
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl animate-in">
        <Card>
          <Notice tone="critical" title="Report could not be generated">{error}</Notice>
          <Link to={`/jobs/${jobId}`} className="btn-secondary mt-4">Back to the result</Link>
        </Card>
      </div>
    )
  }

  const meta = verdictMeta(result?.verdict)

  return (
    <div className="mx-auto max-w-3xl animate-in space-y-5">
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight text-ink-primary">
          Forensic report ready
        </h1>
        <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-ink-secondary">
          Attach this PDF to a complaint filed with your local cybercrime unit or national
          reporting portal. This platform does not file the complaint for you.
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-muted">
              Report reference
            </p>
            <p className="mono mt-1 text-[0.9375rem] font-medium text-ink-primary">
              {report?.report_reference}
            </p>
          </div>
          <Badge tone={meta.tone} icon={meta.icon}>{meta.short}</Badge>
        </div>

        <dl className="mt-5 grid gap-x-8 gap-y-4 border-t pt-5 sm:grid-cols-2"
            style={{ borderColor: 'var(--border-subtle)' }}>
          <Field label="Analysed file">{result?.original_filename}</Field>
          <Field label="Result">
            {percent(result?.fake_probability)} probability of manipulation
          </Field>
          <Field label="Generated">{formatDate(report?.generated_at)}</Field>
          <Field label="Case reference" mono>{result?.case_reference}</Field>
          <Field label="SHA-256 of this report" mono wide>
            <span className="flex items-start gap-2">
              <span className="min-w-0 flex-1">{report?.sha256}</span>
              <CopyButton value={report?.sha256} />
            </span>
          </Field>
        </dl>

        <div className="mt-5 flex flex-wrap gap-3 border-t pt-5"
             style={{ borderColor: 'var(--border-subtle)' }}>
          <button onClick={download} className="btn-primary btn-lg" disabled={downloading}>
            {downloading ? <><Spinner size={16} /> Preparing…</>
              : downloaded ? <><Check size={16} /> Downloaded</>
              : <><Download size={16} /> Download PDF</>}
          </button>
          <Link to={`/jobs/${jobId}`} className="btn-secondary btn-lg">Back to the result</Link>
        </div>
      </Card>

      <div className="grid gap-5 md:grid-cols-2">
        <Card title="What is inside the report">
          <ol className="space-y-2">
            {SECTIONS.map((section, index) => (
              <li key={section}
                  className="flex gap-2.5 text-[0.8125rem] leading-relaxed text-ink-secondary">
                <span className="tnum mt-px shrink-0 font-semibold text-ink-muted">
                  {index + 1}.
                </span>
                {section}
              </li>
            ))}
          </ol>
        </Card>

        <Card title="Verifying this report"
              subtitle="Anyone receiving the PDF can confirm it has not been altered">
          <p className="text-[0.8125rem] leading-relaxed text-ink-secondary">
            Hash the file and compare it against the value published by the register endpoint.
          </p>

          <div className="mt-3 space-y-2">
            {[
              { os: 'Linux / macOS', command: 'shasum -a 256 report.pdf' },
              { os: 'Windows', command: 'certutil -hashfile report.pdf SHA256' },
            ].map((entry) => (
              <div key={entry.os} className="rounded-lg p-2.5"
                   style={{ background: 'var(--surface-2)' }}>
                <p className="text-[0.6875rem] font-medium text-ink-muted">{entry.os}</p>
                <code className="mono mt-1 block overflow-x-auto whitespace-nowrap
                                 text-[0.6875rem] text-ink-secondary">
                  {entry.command}
                </code>
              </div>
            ))}
          </div>

          <div className="mt-3 rounded-lg p-2.5" style={{ background: 'var(--surface-2)' }}>
            <p className="flex items-center gap-1.5 text-[0.6875rem] font-medium text-ink-muted">
              <Hash size={12} /> Register endpoint
            </p>
            {/* break-words, not break-all: keeps the path readable rather than
                splitting the reference mid-token. */}
            <code className="mono mt-1 block break-words text-[0.6875rem] text-ink-secondary">
              /api/reports/{report?.report_reference}/verify
            </code>
          </div>

          <p className="mt-3 text-[0.75rem] leading-relaxed text-ink-muted">
            That endpoint is public and needs no account, so an investigating officer can check
            the report without access to your submission.
          </p>
        </Card>
      </div>

      <Notice tone="info">
        Complaint procedures differ by jurisdiction. Confirm the current process with your local
        cybercrime unit or national reporting portal before submitting.{' '}
        <Link to="/analyse" className="link inline-flex items-center gap-1 whitespace-nowrap">
          Analyse another file <ArrowRight size={12} />
        </Link>
      </Notice>
    </div>
  )
}
