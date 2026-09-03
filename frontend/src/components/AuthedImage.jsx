import { useEffect, useState } from 'react'
import { getToken } from '../lib/api'

/**
 * Loads an image from an endpoint that requires the Authorization header.
 *
 * A plain <img src> cannot send headers, so evidence images belonging to a
 * signed-in user's job would 404. Fetching the bytes and handing the element an
 * object URL is what makes them display.
 */
export default function AuthedImage({ src, alt, className }) {
  const [objectUrl, setObjectUrl] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let revoked = false
    let created = null

    async function load() {
      try {
        const token = getToken()
        const response = await fetch(src, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (!response.ok) throw new Error(`Evidence image unavailable (${response.status})`)
        created = URL.createObjectURL(await response.blob())
        if (!revoked) setObjectUrl(created)
      } catch {
        if (!revoked) setFailed(true)
      }
    }
    load()

    return () => {
      revoked = true
      if (created) URL.revokeObjectURL(created)
    }
  }, [src])

  if (failed) {
    return (
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
        This evidence image could not be loaded. The numeric score above is unaffected.
      </p>
    )
  }
  if (!objectUrl) {
    return <div className={`animate-pulse rounded-lg bg-slate-100 ${className}`} style={{ minHeight: '8rem' }} />
  }
  return <img src={objectUrl} alt={alt} className={className} />
}
