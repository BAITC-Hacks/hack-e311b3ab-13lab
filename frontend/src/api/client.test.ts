import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, errorMessage, getJson, getToken, onUnauthorized, setToken } from './client'

function reply(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
}

describe('api client', () => {
  afterEach(() => setToken(''))

  it('turns validation errors into a readable message', () => {
    expect(errorMessage([{ msg: 'Field required' }, { msg: 'Too short' }], 422)).toBe('Проверьте поля: Field required; Too short')
    expect(errorMessage('Недостаточно прав', 403)).toBe('Недостаточно прав')
    expect(errorMessage(undefined, 500)).toBe('Ошибка запроса (500)')
  })

  it('sends the bearer token', async () => {
    setToken('secret-token')
    const fetchMock = reply(200, { ok: true })
    vi.stubGlobal('fetch', fetchMock)
    await getJson('/api/auth/me')
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer secret-token')
  })

  it('drops the session and notifies listeners on 401', async () => {
    setToken('expired')
    vi.stubGlobal('fetch', reply(401, { detail: 'Сессия истекла. Войдите снова.' }))
    const listener = vi.fn()
    const unsubscribe = onUnauthorized(listener)
    await expect(getJson('/api/meetings')).rejects.toEqual(new ApiError('Сессия истекла. Войдите снова.', 401))
    expect(listener).toHaveBeenCalledOnce()
    expect(getToken()).toBe('')
    unsubscribe()
  })

  it('reports an unreachable server', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(getJson('/api/health')).rejects.toMatchObject({ status: 0 })
  })
})
