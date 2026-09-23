import { vi } from 'vitest'

type Handler = { status?: number; body?: unknown } | ((init: RequestInit | undefined) => { status?: number; body?: unknown })

/** Stub fetch with per-route answers, e.g. { 'POST /api/auth/login': { status: 401, body: {...} } }. */
export function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const path = url.replace(/^https?:\/\/[^/]+/, '')
    const handler = routes[`${init?.method ?? 'GET'} ${path.split('?')[0]}`]
    if (!handler) return new Response(JSON.stringify({ detail: `unmocked ${path}` }), { status: 404 })
    const { status = 200, body = {} } = typeof handler === 'function' ? handler(init) : handler
    return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
