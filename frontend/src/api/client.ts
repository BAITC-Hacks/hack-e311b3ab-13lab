const TOKEN_KEY = 'hattama-token'

function readStoredToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

let token = readStoredToken()
const unauthorizedListeners = new Set<() => void>()

export function getToken(): string {
  return token
}

export function setToken(value: string): void {
  token = value
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage can be unavailable in private windows; the in-memory token still works.
  }
}

/** Called when the server rejects the current session, e.g. after expiry or deactivation. */
export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener)
  return () => unauthorizedListeners.delete(listener)
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : ''))
      .filter(Boolean)
    if (messages.length) return `Проверьте поля: ${messages.join('; ')}`
  }
  if (status === 0) return 'Сервер недоступен. Проверьте подключение.'
  return `Ошибка запроса (${status})`
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  json?: unknown
  body?: FormData
  signal?: AbortSignal
}

export async function request(path: string, options: RequestOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined = options.body
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  }
  let response: Response
  try {
    response = await fetch(path, { method: options.method ?? 'GET', headers, body, signal: options.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(errorMessage(undefined, 0), 0)
  }
  if (!response.ok) {
    const data: { detail?: unknown } = await response.json().catch(() => ({}))
    if (response.status === 401 && token && path !== '/api/auth/login') {
      setToken('')
      unauthorizedListeners.forEach((listener) => listener())
    }
    throw new ApiError(errorMessage(data.detail, response.status), response.status)
  }
  return response
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await request(path, { signal })).json() as Promise<T>
}

export async function sendJson<T>(path: string, method: RequestOptions['method'], json?: unknown): Promise<T> {
  const response = await request(path, { method, json })
  return (response.status === 204 ? undefined : await response.json()) as T
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const blob = await (await request(path)).blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
