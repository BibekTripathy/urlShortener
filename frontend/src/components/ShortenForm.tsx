import { useState, type FormEvent } from 'react'
import { createLink, type Link } from '../api'

export function ShortenForm({ onCreated }: { onCreated: (l: Link) => void }) {
  const [url, setUrl] = useState('')
  const [alias, setAlias] = useState('')
  const [days, setDays] = useState('')
  const [showOpts, setShowOpts] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const link = await createLink({
        url: url.trim(),
        alias: alias.trim() || undefined,
        expires_in_days: days ? Number(days) : undefined,
      })
      onCreated(link)
      setUrl('')
      setAlias('')
      setDays('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="card" noValidate>
      <div className="row">
        <input
          type="url"
          placeholder="https://your-long-link.com/goes/here"
          aria-label="Long URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          autoFocus
        />
        <button type="submit" disabled={busy || !url.trim()}>
          {busy ? 'Shortening…' : 'Shorten'}
        </button>
      </div>

      <button type="button" className="link" onClick={() => setShowOpts((v) => !v)}
        aria-expanded={showOpts}>
        {showOpts ? '− Options' : '+ Options'}
      </button>

      {showOpts && (
        <div className="row opts">
          <label>
            Custom alias
            <input value={alias} onChange={(e) => setAlias(e.target.value)} placeholder="my-link" />
          </label>
          <label>
            Expires in (days)
            <input type="number" min={1} max={3650} value={days}
              onChange={(e) => setDays(e.target.value)} placeholder="never" />
          </label>
        </div>
      )}

      {error && <p role="alert" className="error">{error}</p>}
    </form>
  )
}
