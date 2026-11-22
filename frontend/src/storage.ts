import type { Link } from './api'

const KEY = 'shrt.recent'
const MAX = 8

export function loadRecent(): Link[] {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Link[]) : []
  } catch {
    return []
  }
}

export function saveRecent(links: Link[]): Link[] {
  const trimmed = links.slice(0, MAX)
  try {
    localStorage.setItem(KEY, JSON.stringify(trimmed))
  } catch {
    /* storage unavailable: keep in memory only */
  }
  return trimmed
}
