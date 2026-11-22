export interface Link {
  code: string
  short_url: string
  url: string
  clicks: number
  created_at: string
  expires_at: string | null
}

export interface CreateLinkInput {
  url: string
  alias?: string
  expires_in_days?: number
}

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    const msg = Array.isArray(detail)
      ? detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join('; ')
      : typeof detail === 'string'
        ? detail
        : `Request failed (${res.status})`
    throw new ApiError(res.status, msg)
  }
  return body as T
}

export const createLink = (input: CreateLinkInput) =>
  request<Link>('/api/v1/links', { method: 'POST', body: JSON.stringify(input) })

export const getLink = (code: string) =>
  request<Link>(`/api/v1/links/${encodeURIComponent(code)}`)
