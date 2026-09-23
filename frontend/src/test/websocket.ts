import { vi } from 'vitest'

/** Minimal WebSocket stand-in that tests drive with `emit`. */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static readonly OPEN = 1
  readyState = 0
  sent: unknown[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  binaryType = 'blob'

  constructor(public url: string) {
    FakeWebSocket.instances.push(this)
    setTimeout(() => {
      this.readyState = 1
      this.onopen?.()
    })
  }

  send(data: unknown) {
    this.sent.push(data)
  }

  close() {
    this.readyState = 3
  }

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) })
  }
}

export function installFakeWebSocket() {
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
  return FakeWebSocket
}
