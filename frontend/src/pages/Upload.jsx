import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { formatBytes } from '../lib/format'
import { useAuth } from '../lib/useAuth'
import { Card, Notice } from '../components/ui'
import { ArrowRight, MEDIA_ICON, Spinner, Upload as UploadIcon } from '../components/ui/Icons'

const KIND_BY_EXTENSION = (limits) => {
  const map = {}
  Object.entries(limits?.allowed_extensions || {}).forEach(([kind, list]) =>
    list.forEach((ext) => { map[ext] = kind }))
  return map
}

export default function UploadPage() {
  const [limits, setLimits] = useState(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [phase, setPhase] = useState('idle')
  const [error, setError] = useState(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()
  const { user } = useAuth()

  useEffect(() => {
    api.limits().then(setLimits).catch(() => setLimits(null))
  }, [])

  // Revoke the object URL when the selection changes, or the browser leaks it.
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const extensions = limits
    ? Object.values(limits.allowed_extensions).flat()
    : ['.jpg', '.png', '.wav', '.mp3', '.mp4', '.mov']
  const kinds = KIND_BY_EXTENSION(limits)

  function validate(candidate) {
    const suffix = candidate.name.slice(candidate.name.lastIndexOf('.')).toLowerCase()
    if (!extensions.includes(suffix)) {
      return `Unsupported file type “${suffix || 'unknown'}”. Accepted: ${extensions.join(', ')}`
    }
    if (limits && candidate.size > limits.max_upload_mb * 1024 * 1024) {
      return `This file is ${formatBytes(candidate.size)}; the limit is ${limits.max_upload_mb} MB.`
    }
    return null
  }

  function choose(candidate) {
    if (!candidate) return
    const problem = validate(candidate)
    setError(problem)
    if (problem) { setFile(null); setPreview(null); return }
    setFile(candidate)
    setPreview(candidate.type.startsWith('image/') ? URL.createObjectURL(candidate) : null)
  }

  async function submit() {
    if (!file) return
    setError(null)
    setPhase('uploading')
    setProgress(0)
    try {
      const job = await api.upload(file, setProgress)
      navigate(`/jobs/${job.id}`)
    } catch (err) {
      setError(err.message)
      setPhase('idle')
    }
  }

  const suffix = file ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase() : null
  const MediaIcon = MEDIA_ICON[kinds[suffix]] || UploadIcon

  return (
    <div className="mx-auto max-w-2xl animate-in space-y-5">
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight text-ink-primary">Analyse a file</h1>
        <p className="mt-1.5 text-[0.9375rem] text-ink-secondary">
          Your file is hashed on arrival and stored unchanged, so the report can attest to exactly
          what was analysed.
        </p>
      </div>

      <div
        className={`card relative cursor-pointer overflow-hidden border-2 border-dashed p-8
                    text-center transition-all duration-200 ${dragging ? 'scale-[1.01]' : ''}`}
        style={{
          borderColor: dragging ? 'var(--accent)' : 'var(--border-strong)',
          background: dragging ? 'var(--accent-soft)' : 'var(--surface-1)',
        }}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files?.[0]) }}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Choose a file to analyse"
      >
        <input ref={inputRef} type="file" className="hidden" accept={extensions.join(',')}
               onChange={(e) => choose(e.target.files?.[0])} />

        {file ? (
          <div className="flex flex-col items-center">
            {preview ? (
              <img src={preview} alt="" className="mb-4 max-h-40 rounded-lg object-contain shadow-sm" />
            ) : (
              <span className="mb-4 grid h-14 w-14 place-items-center rounded-xl"
                    style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
                <MediaIcon size={26} />
              </span>
            )}
            <p className="max-w-full truncate font-semibold text-ink-primary">{file.name}</p>
            <p className="tnum mt-1 text-[0.8125rem] text-ink-muted">
              {formatBytes(file.size)}
              {kinds[suffix] ? ` · ${kinds[suffix]}` : ''}
            </p>
            <p className="mt-3 text-[0.75rem] text-ink-muted">Click to choose a different file</p>
          </div>
        ) : (
          <div className="flex flex-col items-center py-3">
            <span className="grid h-14 w-14 place-items-center rounded-xl"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
              <UploadIcon size={26} />
            </span>
            <p className="mt-4 font-semibold text-ink-primary">
              Drop a file here, or click to browse
            </p>
            <p className="mt-1.5 text-[0.8125rem] text-ink-muted">
              Images{limits ? ` · up to ${limits.max_upload_mb} MB` : ''}
            </p>
            <p className="mono mt-3 text-[0.6875rem] text-ink-muted">{extensions.join('  ')}</p>
          </div>
        )}
      </div>

      {error && <Notice tone="critical" title="File not accepted">{error}</Notice>}

      {phase === 'uploading' && (
        <Card>
          <div className="flex items-center justify-between text-[0.8125rem]">
            <span className="font-medium text-ink-primary">
              {progress < 100 ? 'Uploading…' : 'Upload complete — queueing analysis'}
            </span>
            <span className="tnum text-ink-muted">{progress}%</span>
          </div>
          <div className="mt-2.5 h-1.5 overflow-hidden rounded-full"
               style={{ background: 'var(--surface-3)' }}>
            <div className="h-full rounded-full transition-all duration-200"
                 style={{ width: `${progress}%`, background: 'var(--accent)' }} />
          </div>
        </Card>
      )}

      <button className="btn-primary w-full !py-3" onClick={submit}
              disabled={!file || phase !== 'idle'}>
        {phase === 'idle'
          ? <>Start analysis <ArrowRight size={16} /></>
          : <><Spinner size={16} /> Working…</>}
      </button>

      {limits && (
        <p className="text-center text-[0.75rem] text-ink-muted">
          {user
            ? `Upload limit: ${limits.rate_limit_per_hour.registered} files per hour.`
            : `Guest limit: ${limits.rate_limit_per_hour.guest} files per hour — sign in for ${limits.rate_limit_per_hour.registered}.`}
        </p>
      )}
    </div>
  )
}
