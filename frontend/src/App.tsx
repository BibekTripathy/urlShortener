import { useEffect, useState } from 'react'
import { getLink, type Link } from './api'
import { LinkList } from './components/LinkList'
import { ShortenForm } from './components/ShortenForm'
import { loadRecent, saveRecent } from './storage'

export default function App() {
  const [links, setLinks] = useState<Link[]>(loadRecent)

  // refresh click counts once on load
  useEffect(() => {
    const initial = loadRecent()
    if (initial.length === 0) return
    Promise.allSettled(initial.map((l) => getLink(l.code))).then((rs) => {
      const fresh = rs.flatMap((r) => (r.status === 'fulfilled' ? [r.value] : []))
      setLinks(saveRecent(fresh))
    })
  }, [])

  const add = (l: Link) => setLinks((prev) => saveRecent([l, ...prev.filter((p) => p.code !== l.code)]))

  return (
    <main>
      <header>
        <h1>shrt</h1>
        <p className="sub">Short links, fast redirects.</p>
      </header>
      <ShortenForm onCreated={add} />
      <LinkList links={links} />
      <footer>
        <a href="/docs">API</a>
      </footer>
    </main>
  )
}
