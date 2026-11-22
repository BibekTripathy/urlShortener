import type { Link } from '../api'
import { CopyButton } from './CopyButton'

export function LinkList({ links }: { links: Link[] }) {
  if (links.length === 0) return null
  return (
    <section aria-label="Recent links">
      <h2>Recent</h2>
      <ul className="links">
        {links.map((l) => (
          <li key={l.code}>
            <div className="meta">
              <a href={l.short_url} target="_blank" rel="noreferrer" className="short">
                {l.short_url.replace(/^https?:\/\//, '')}
              </a>
              <span className="long" title={l.url}>{l.url}</span>
            </div>
            <span className="clicks">{l.clicks} clicks</span>
            <CopyButton text={l.short_url} />
          </li>
        ))}
      </ul>
    </section>
  )
}
