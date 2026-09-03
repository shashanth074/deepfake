import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, connectJobWs } from '../lib/api'
import { formatBytes, formatDate, formatDuration, percent, verdictMeta } from '../lib/format'
import AuthedImage from '../components/AuthedImage'
import ConfidenceChart from '../components/ConfidenceChart'
import {
  Card, CopyButton, Field, Notice, ProbabilityMeter, Stat,
} from '../components/ui'
import { ArrowRight, FileText, MEDIA_ICON, Upload } from '../components/ui/Icons'

const STAGE_LABELS = {
  queued:     'Waiting in queue\u2026',
  processing: 'Running analysis\u2026',
  done:       'Analysis complete.',
  failed:     'Analysis failed.',
}

export default function Result() {
  const { jobId } = useParams()
  const [result, setResult] = useState(null)
  const [liveStatus, setLiveStatus] = useState({ status: 'queued', progress_pct: 5, message: 'Waiting in queue\u2026' })
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true

    connectJobWs(jobId, {
      onTick: (tick) => {
        if (!active) return
        setLiveStatus({
          status: tick.status,
          progress_pct: tick.progress_pct ?? 0,
          message: STAGE_LABELS[tick.status] ?? tick.message ?? tick.status,
        })
      },
      onError: () => {
        // WS failed -- polling takes over silently; liveStatus stays as-is
      },
    })
      .then((payload) => { if (active) setResult(payload) })
      .catch((err)   => { if (active) setError(err.message) })

    return () => { active = false }
  }, [jobId])

  // ------------------------------------------------------------------ error
  if (error) {
    return (
      <div className="mx-auto max-w-xl animate-in">
        <Card>
          <Notice tone="critical" title="Analysis could not be completed">{error}</Notice>
          <Link to="/analyse" className="btn-secondary mt-4">
            <Upload size={15} /> Try another file
          </Link>
        </Card>
      </div>
    )
  }

  // ------------------------------------------------------------------ loading
  if (!result) {
    const pct = liveStatus.progress_pct ?? 0
    return (
      <div className="mx-auto max-w-4xl animate-in space-y-6">
        {/* Progress Banner */}
        <div className="card overflow-hidden border-2 transition-colors duration-500" 
             style={{ borderColor: pct === 100 ? 'var(--status-good)' : 'var(--accent-ring)' }}>
          <div className="relative overflow-hidden p-8 text-center" style={{ background: 'var(--surface-1)' }}>
             {/* A subtle animated background glow */}
             <div className="pointer-events-none absolute inset-0 opacity-[0.08] transition-opacity duration-1000"
                  style={{ background: 'radial-gradient(circle at 50% -20%, var(--accent), transparent 70%)' }} />
             
            <h2 className="mb-2 text-2xl font-bold tracking-tight text-ink-primary">
              {liveStatus.message}
            </h2>
            
            <div className="mb-8 flex items-center justify-center gap-1.5 text-sm text-ink-muted">
              <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full"
                    style={{ background: 'var(--accent)', animationDelay: '0ms' }} />
              <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full"
                    style={{ background: 'var(--accent)', animationDelay: '150ms' }} />
              <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full"
                    style={{ background: 'var(--accent)', animationDelay: '300ms' }} />
              <span className="ml-1">Analysing deepfake features in real time&hellip;</span>
            </div>

            <div className="relative mx-auto max-w-lg">
              <div className="mb-2 flex justify-between px-1 text-xs font-medium text-ink-muted">
                <span>{pct === 100 ? 'Finalizing report' : 'Extracting evidence'}</span>
                <span className="tnum">{pct}%</span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full shadow-inner" style={{ background: 'var(--surface-3)' }}>
                <div
                  className="relative h-full rounded-full transition-all duration-700 ease-out"
                  style={{
                    width: `${pct}%`,
                    background: pct === 100
                      ? 'var(--status-good)'
                      : 'linear-gradient(90deg, var(--accent), #818cf8)',
                  }}
                >
                  <div className="absolute inset-0 animate-pulse bg-white/20" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Skeleton Layout to build anticipation */}
        <div className="pointer-events-none space-y-5 opacity-50 transition-opacity duration-1000">
          {/* Verdict Skeleton */}
          <section className="card flex flex-wrap items-start justify-between gap-4 p-6">
            <div className="flex w-2/3 gap-4">
              <div className="skeleton h-12 w-12 rounded-xl" />
              <div className="w-full space-y-3">
                <div className="skeleton h-3 w-20 rounded" />
                <div className="skeleton h-8 w-64 rounded" />
                <div className="skeleton h-4 w-3/4 rounded" />
              </div>
            </div>
            <div className="space-y-2 text-right">
              <div className="skeleton ml-auto h-10 w-24 rounded" />
              <div className="skeleton ml-auto h-3 w-32 rounded" />
            </div>
          </section>

          {/* Details Skeleton */}
          <section className="card p-6">
            <div className="skeleton mb-6 h-5 w-40 rounded" />
            <div className="grid grid-cols-2 gap-x-8 gap-y-6">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="space-y-2.5">
                  <div className="skeleton h-3 w-20 rounded" />
                  <div className="skeleton h-4 w-48 rounded" />
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    )
  }

  // ------------------------------------------------------------------ result
  const meta = verdictMeta(result.verdict)
  const evidence = result.evidence || {}
  const timeline = evidence.frame_scores || evidence.segment_scores || []
  const MediaIcon = MEDIA_ICON[result.media_type] || FileText
  const untrained = result.weights_status && result.weights_status !== 'trained'

  const evidenceSubtitle = evidence.heatmap_url
    ? 'Regions that most influenced the model decision'
    : evidence.spectrogram_url
      ? 'Frequency content over time, with flagged windows marked'
      : 'Per-frame manipulation probability over time'

  return (
    <div className="mx-auto max-w-4xl animate-in space-y-5">
      {untrained && (
        <Notice tone="critical" title="Demonstration mode -- this score is not evidence">
          No trained model checkpoint is installed on this deployment, so the network is running
          with untrained weights. The score below carries no evidentiary value. Train the
          detectors or install checkpoints before relying on any report from this instance.
        </Notice>
      )}

      {/* ---------------------------------------------------------- verdict */}
      <section className="card overflow-hidden">
        <div className="p-6" style={{ background: meta.bg }}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <span className="mt-0.5 shrink-0" style={{ color: meta.color }}>
                <meta.icon size={32} />
              </span>
              <div>
                <p className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-muted">
                  Verdict
                </p>
                <h1 className="mt-0.5 text-[1.75rem] font-bold leading-tight tracking-tight"
                    style={{ color: meta.color }}>
                  {meta.label}
                </h1>
                <p className="mt-1.5 max-w-md text-[0.875rem] leading-relaxed text-ink-secondary">
                  {meta.blurb}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="tnum text-[2.5rem] font-extrabold leading-none tracking-tightest"
                 style={{ color: meta.color }}>
                {percent(result.fake_probability)}
              </p>
              <p className="mt-1 text-[0.75rem] text-ink-muted">probability of manipulation</p>
            </div>
          </div>
        </div>

        <div className="border-t p-6" style={{ borderColor: 'var(--border-subtle)' }}>
          <ProbabilityMeter value={result.fake_probability} />
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <Stat label="Decision confidence" value={percent(result.confidence)}
                  hint="Distance from the undecided midpoint" />
            <Stat label="Processing time" value={formatDuration(result.processing_ms)}
                  hint="End to end" />
            <Stat label="Media analysed"
                  value={result.media_type.charAt(0).toUpperCase() + result.media_type.slice(1)}
                  hint={evidence.faces_detected !== undefined
                        ? `${evidence.faces_detected} face(s) detected`
                        : evidence.frames_analysed
                          ? `${evidence.frames_analysed} frames sampled`
                          : `${evidence.segments_analysed || 0} windows`} />
          </div>
          <p className="mt-4 text-[0.75rem] leading-relaxed text-ink-muted">
            A score near 50% means the model cannot separate this file from authentic media. That
            is reported as inconclusive rather than forced into a yes or no.
          </p>
        </div>
      </section>

      {/* ------------------------------------------------------ file details */}
      <Card title="Submitted file"
            subtitle="Recorded at the moment of upload, before any processing">
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          <Field label="Filename">
            <span className="flex items-center gap-2">
              <span className="text-ink-muted"><MediaIcon size={15} /></span>
              <span className="truncate">{result.original_filename}</span>
            </span>
          </Field>
          <Field label="Case reference" mono>{result.case_reference}</Field>
          <Field label="File size">{formatBytes(result.file_size_bytes)}</Field>
          <Field label="Received">{formatDate(result.uploaded_at)}</Field>
          <Field label="Model">
            {result.model_name}
            <span className="mono ml-1.5 text-[0.75rem] text-ink-muted">
              {result.model_version}
            </span>
          </Field>
          <Field label="Weights">
            <span style={{ color: untrained ? 'var(--status-critical)' : 'var(--status-good)' }}>
              {untrained ? 'Untrained -- not evidential' : 'Trained checkpoint'}
            </span>
          </Field>
          <Field label="SHA-256 of the analysed file" mono wide>
            <span className="flex items-start gap-2">
              <span className="min-w-0 flex-1">{result.sha256}</span>
              <CopyButton value={result.sha256} />
            </span>
          </Field>
        </dl>
      </Card>

      {/* --------------------------------------------------------- evidence */}
      {(evidence.heatmap_url || evidence.spectrogram_url || evidence.timeline_url) && (
        <Card title="Visual evidence" subtitle={evidenceSubtitle}>
          {evidence.heatmap_url && (
            <figure>
              <div className="flex justify-center rounded-lg p-5"
                   style={{ background: 'var(--surface-2)' }}>
                <AuthedImage src={api.evidenceUrl(evidence.heatmap_url)}
                             alt="Grad-CAM heatmap over the analysed region"
                             className="max-h-[22rem] rounded-md shadow-md" />
              </div>
              <figcaption className="mt-3 text-[0.75rem] leading-relaxed text-ink-muted">
                Grad-CAM heatmap. Warmer areas contributed most strongly to the decision &mdash; on a
                face swap these commonly appear along the jawline, hairline, or the boundary
                where a synthetic face was blended into the original.
              </figcaption>
            </figure>
          )}
          {evidence.spectrogram_url && (
            <figure>
              <AuthedImage src={api.evidenceUrl(evidence.spectrogram_url)}
                           alt="Log-Mel spectrogram with flagged windows outlined"
                           className="w-full rounded-lg" />
              <figcaption className="mt-3 text-[0.75rem] leading-relaxed text-ink-muted">
                Log-Mel spectrogram. Red boxes mark the windows scored as synthetic.
              </figcaption>
            </figure>
          )}
          {evidence.timeline_url && (
            <figure>
              <AuthedImage src={api.evidenceUrl(evidence.timeline_url)}
                           alt="Per-frame manipulation probability timeline"
                           className="w-full rounded-lg" />
              <figcaption className="mt-3 text-[0.75rem] leading-relaxed text-ink-muted">
                Per-frame confidence curve. Peaks indicate frames where the model suspects
                manipulation &mdash; a consistent high score across the clip is stronger evidence
                than an isolated spike.
              </figcaption>
            </figure>
          )}
        </Card>
      )}

      {/* --------------------------------------------------------- timeline chart */}
      {timeline.length > 1 && (
        <Card
          title={evidence.frame_scores ? 'Per-frame confidence' : 'Per-window confidence'}
          subtitle="A manipulation affecting only part of the media appears here as a localised peak"
        >
          <ConfidenceChart points={timeline}
                           unit={evidence.frame_scores ? 'Frame' : 'Window'} />
        </Card>
      )}

      {/* ------------------------------------------------------------ notes */}
      {evidence.notes?.length > 0 && (
        <Card title="Analysis notes">
          <ul className="space-y-2">
            {evidence.notes.map((note) => (
              <li key={note} className="flex gap-2.5 text-[0.8125rem] leading-relaxed text-ink-secondary">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full"
                      style={{ background: 'var(--text-muted)' }} />
                {note}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="flex flex-wrap gap-3">
        <Link to={`/jobs/${jobId}/report`} className="btn-primary btn-lg">
          <FileText size={16} /> Generate forensic report <ArrowRight size={15} />
        </Link>
        <Link to="/analyse" className="btn-secondary btn-lg">
          <Upload size={15} /> Analyse another file
        </Link>
      </div>

      <Notice tone="warn" title="Read this before relying on the result">
        This is an automated technical assessment, not a certified forensic opinion. Detectors
        produce both false positives and false negatives, and accuracy degrades on compressed or
        low-resolution media. For legal proceedings, verification by a certified forensic expert
        is recommended.
      </Notice>
    </div>
  )
}
