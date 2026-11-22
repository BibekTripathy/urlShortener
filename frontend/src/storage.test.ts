import { describe, expect, it } from 'vitest'
import { loadRecent, saveRecent } from './storage'

const mk = (code: string) => ({ code, short_url: '', url: '', clicks: 0, created_at: '', expires_at: null })

describe('storage', () => {
  it('returns [] for empty or corrupt storage', () => {
    expect(loadRecent()).toEqual([])
    localStorage.setItem('shrt.recent', '{bad json')
    expect(loadRecent()).toEqual([])
  })
  it('caps the list at 8 entries', () => {
    saveRecent(Array.from({ length: 12 }, (_, i) => mk(String(i))))
    expect(loadRecent()).toHaveLength(8)
  })
})
