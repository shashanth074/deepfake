import { useEffect, useState } from 'react'
import { Card, Notice } from '../components/ui'
import { Image, Video, Waveform } from '../components/ui/Icons'
import { api } from '../lib/api'

const PIPELINES = [
  {
    icon: Image,
    media: 'Images',
    steps: [
      'Faces are detected and cropped with a margin (MTCNN).',
      'Each crop is resized and normalised to the network’s input resolution.',
      'A CNN backbone (EfficientNet or Xception) scores the crop.',
    ],
  },
]

const LIMITS = [
  'Accuracy drops on heavily compressed or low-resolution media — social platforms recompress everything.',
  'A model generalises poorly to manipulation techniques absent from its training data, and new generators appear constantly.',
  'Media with no visible face gives the image and video detectors far less to work with.',
  'Faces that occupy less than 5% of the frame are ignored to prevent false positives.',
]

export default function HowItWorks() {
  const [health, setHealth] = useState(null)

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)) }, [])

  return (
    <div className="mx-auto max-w-3xl animate-in space-y-5">
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight text-ink-primary">How it works</h1>
        <p className="mt-1.5 text-[0.9375rem] text-ink-secondary">
          Each medium gets its own pipeline. All of them end in a probability, not a verdict
          asserted as fact.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {PIPELINES.map((pipeline) => (
          <Card key={pipeline.media}>
            <div className="flex items-center gap-2.5">
              <span className="text-accent"><pipeline.icon size={18} /></span>
              <h2 className="panel-title">{pipeline.media}</h2>
            </div>
            <ol className="mt-3.5 space-y-2.5">
              {pipeline.steps.map((step, index) => (
                <li key={step} className="flex gap-2.5 text-[0.8125rem] leading-relaxed text-ink-secondary">
                  <span className="tnum mt-px shrink-0 font-semibold text-ink-muted">
                    {index + 1}.
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </Card>
        ))}
      </div>

      <Card title="Training data"
            subtitle="Public academic corpora, split to avoid inflating the reported accuracy">
        <p className="text-[0.8125rem] leading-relaxed text-ink-secondary">
          We currently score against the FFHQ and 140k Real and Fake Faces datasets. Data is split by source video and by speaker — never by
          frame — so the same identity cannot appear in both the training and test sets. Splitting
          by frame is the most common way student projects overstate their accuracy.
        </p>
      </Card>

      <Card title="Known limitations" subtitle="Stated here because they affect how you should read a result">
        <ul className="space-y-2.5">
          {LIMITS.map((limit) => (
            <li key={limit} className="flex gap-2.5 text-[0.8125rem] leading-relaxed text-ink-secondary">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full"
                    style={{ background: 'var(--text-muted)' }} />
              {limit}
            </li>
          ))}
        </ul>
      </Card>

      {health && (
        <Card title="This deployment" subtitle="Live status of the models serving your requests">
          <dl className="space-y-2.5 text-[0.8125rem]">
            <div className="flex flex-wrap gap-x-3">
              <dt className="w-28 shrink-0 text-ink-muted">Platform</dt>
              <dd className="mono text-ink-primary">v{health.version}</dd>
            </div>
            <div className="flex flex-wrap gap-x-3">
              <dt className="w-28 shrink-0 text-ink-muted">Queue</dt>
              <dd className="text-ink-primary">
                {health.queue_enabled ? 'Celery worker' : 'inline (development)'}
              </dd>
            </div>
            {Object.entries(health.models || {}).map(([key, value]) => (
              <div key={key} className="flex flex-wrap gap-x-3">
                <dt className="w-28 shrink-0 capitalize text-ink-muted">{key} model</dt>
                <dd className="mono min-w-0 flex-1 text-[0.75rem] text-ink-secondary">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <Notice tone="warn" title="What this tool is not">
        It provides an automated technical assessment, not a certified forensic opinion, and it
        does not file complaints with any authority. Serious matters are typically escalated to a
        government forensic laboratory; treat this output as an investigative lead.
      </Notice>
    </div>
  )
}
