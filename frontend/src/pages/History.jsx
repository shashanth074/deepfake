import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { formatDate, percent, verdictMeta } from '../lib/format'
import { Badge, Card, EmptyState, Notice, Skeleton } from '../components/ui'
import { History as HistoryIcon, MEDIA_ICON, Trash, Upload } from '../components/ui/Icons'

const PAGE_SIZE = 20

export default function History() {
  const [page, setPage] = useState({ items: [], total: 0, offset: 0 })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(async (offset = 0) => {
    setLoading(true)
    try {
      setPage(await api.history(PAGE_SIZE, offset))
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(0) }, [load])

  async function remove(jobId, filename) {
    const confirmed = window.confirm(
      `Delete “${filename}”?\n\nThis permanently erases the stored media, its evidence images ` +
      'and any report generated from it. This cannot be undone.'
    )
    if (!confirmed) return
    setDeleting(jobId)
    try {
      await api.deleteScan(jobId)
      await load(page.offset)
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="mx-auto max-w-5xl animate-in space-y-5">
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-tight text-ink-primary">Scan history</h1>
        <p className="mt-1.5 text-[0.9375rem] text-ink-secondary">
          {loading ? 'Loading…' : `${page.total} ${page.total === 1 ? 'scan' : 'scans'}.`}{' '}
          Deleting a scan also erases the stored media, its evidence images and any report.
        </p>
      </div>

      {error && <Notice tone="critical">{error}</Notice>}

      {loading ? (
        <Card>
          <div className="space-y-3">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        </Card>
      ) : page.items.length === 0 ? (
        <Card pad={false}>
          <EmptyState
            icon={HistoryIcon}
            title="You have not analysed anything yet"
            detail="Uploaded files and their reports will appear here."
            action={<Link to="/analyse" className="btn-primary"><Upload size={15} /> Analyse a file</Link>}
          />
        </Card>
      ) : (
        <Card pad={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[0.8125rem]">
              <thead style={{ background: 'var(--surface-2)' }}>
                <tr className="text-[0.6875rem] uppercase tracking-wider text-ink-muted">
                  <th className="px-5 py-3 font-semibold">File</th>
                  <th className="px-5 py-3 font-semibold">Verdict</th>
                  <th className="px-5 py-3 font-semibold text-right">Score</th>
                  <th className="px-5 py-3 font-semibold">Analysed</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {page.items.map((item) => {
                  const meta = verdictMeta(item.verdict)
                  const MediaIcon = MEDIA_ICON[item.media_type]
                  return (
                    <tr key={item.id} className="divide-row transition-colors hover:bg-surface-2">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2.5">
                          <span className="shrink-0 text-ink-muted">
                            {MediaIcon && <MediaIcon size={16} />}
                          </span>
                          <div className="min-w-0">
                            <Link to={`/jobs/${item.id}`}
                                  className="block truncate font-medium text-ink-primary hover:text-accent">
                              {item.original_filename}
                            </Link>
                            <span className="mono block text-[0.6875rem] text-ink-muted">
                              {item.case_reference}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        {item.status === 'done' ? (
                          <Badge tone={meta.tone} icon={meta.icon}>{meta.short}</Badge>
                        ) : (
                          <Badge>{item.status}</Badge>
                        )}
                      </td>
                      <td className="tnum px-5 py-3 text-right font-medium text-ink-secondary">
                        {percent(item.fake_probability)}
                      </td>
                      <td className="px-5 py-3 text-ink-muted">{formatDate(item.uploaded_at)}</td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={() => remove(item.id, item.original_filename)}
                          disabled={deleting === item.id}
                          className="btn-ghost !px-2 !py-1 text-[0.75rem] hover:!text-status-critical"
                          aria-label={`Delete ${item.original_filename}`}
                        >
                          <Trash size={14} />
                          {deleting === item.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {page.total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-[0.8125rem]">
          <button className="btn-secondary" disabled={page.offset === 0}
                  onClick={() => load(Math.max(0, page.offset - PAGE_SIZE))}>
            Previous
          </button>
          <span className="tnum text-ink-muted">
            {page.offset + 1}–{Math.min(page.offset + PAGE_SIZE, page.total)} of {page.total}
          </span>
          <button className="btn-secondary" disabled={page.offset + PAGE_SIZE >= page.total}
                  onClick={() => load(page.offset + PAGE_SIZE)}>
            Next
          </button>
        </div>
      )}
    </div>
  )
}
