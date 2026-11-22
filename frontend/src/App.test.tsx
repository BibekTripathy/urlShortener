import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const link = {
  code: 'abc1234', short_url: 'http://sho.rt/abc1234', url: 'https://example.com/long',
  clicks: 0, created_at: '2026-01-01T00:00:00Z', expires_at: null,
}

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body })
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('App', () => {
  it('renders the form with submit disabled until a URL is typed', async () => {
    render(<App />)
    const btn = screen.getByRole('button', { name: 'Shorten' })
    expect(btn).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Long URL'), 'https://example.com')
    expect(btn).toBeEnabled()
  })

  it('creates a link via the API and lists it', async () => {
    const fetchMock = mockFetch(201, link)
    render(<App />)
    await userEvent.type(screen.getByLabelText('Long URL'), 'https://example.com/long')
    await userEvent.click(screen.getByRole('button', { name: 'Shorten' }))
    expect(await screen.findByText('sho.rt/abc1234')).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/links')
    expect(JSON.parse(init.body)).toEqual({ url: 'https://example.com/long' })
    expect(JSON.parse(localStorage.getItem('shrt.recent')!)[0].code).toBe('abc1234')
  })

  it('sends alias and expiry options', async () => {
    const fetchMock = mockFetch(201, { ...link, code: 'mine' })
    render(<App />)
    await userEvent.type(screen.getByLabelText('Long URL'), 'https://example.com')
    await userEvent.click(screen.getByRole('button', { name: '+ Options' }))
    await userEvent.type(screen.getByLabelText('Custom alias'), 'mine')
    await userEvent.type(screen.getByLabelText('Expires in (days)'), '7')
    await userEvent.click(screen.getByRole('button', { name: 'Shorten' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      url: 'https://example.com', alias: 'mine', expires_in_days: 7,
    })
  })

  it('shows API error messages', async () => {
    mockFetch(409, { detail: 'alias already taken' })
    render(<App />)
    await userEvent.type(screen.getByLabelText('Long URL'), 'https://example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Shorten' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('alias already taken')
  })

  it('formats validation errors', async () => {
    mockFetch(422, { detail: [{ msg: 'Value error, alias is reserved' }] })
    render(<App />)
    await userEvent.type(screen.getByLabelText('Long URL'), 'https://example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Shorten' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('alias is reserved')
  })

  it('refreshes click counts for stored links on load', async () => {
    localStorage.setItem('shrt.recent', JSON.stringify([link]))
    mockFetch(200, { ...link, clicks: 42 })
    render(<App />)
    expect(await screen.findByText('42 clicks')).toBeInTheDocument()
  })
})
