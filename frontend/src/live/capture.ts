import { sendJson } from '../api/client'

export type CaptureState =
  | { status: 'idle' }
  | { status: 'streaming'; meetingId: string; level: number; startedAt: number; withMic: boolean }
  | { status: 'reconnecting'; meetingId: string; level: number; startedAt: number; withMic: boolean }
  | { status: 'ended'; meetingId: string; reason: string }

type Listener = () => void

export class CaptureError extends Error {}

/** Opens the tab picker. Must run directly in a click handler (transient user activation). */
export async function pickMeetingTab(withMic: boolean): Promise<MediaStream[]> {
  if (!navigator.mediaDevices?.getDisplayMedia) throw new CaptureError('Этот браузер не умеет захватывать звук вкладки. Используйте Chrome или Edge.')
  let display: MediaStream
  try {
    display = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: { suppressLocalAudioPlayback: false } as MediaTrackConstraints })
  } catch {
    throw new CaptureError('Захват отменён. Выберите вкладку совещания и нажмите «Поделиться».')
  }
  if (display.getAudioTracks().length === 0) {
    display.getTracks().forEach((track) => track.stop())
    throw new CaptureError('Во вкладке нет звука. Выберите вкладку (не окно) и включите «Поделиться звуком вкладки».')
  }
  const streams = [display]
  if (withMic) {
    try {
      streams.push(await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }))
    } catch {
      display.getTracks().forEach((track) => track.stop())
      throw new CaptureError('Нет доступа к микрофону. Разрешите его или снимите галочку «Мой микрофон».')
    }
  }
  return streams
}

/** Microphone only: a meeting in a physical room recorded from this computer. */
export async function pickMicrophone(): Promise<MediaStream[]> {
  if (!navigator.mediaDevices?.getUserMedia) throw new CaptureError('Этот браузер не даёт доступ к микрофону.')
  try {
    return [await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })]
  } catch {
    throw new CaptureError('Нет доступа к микрофону. Разрешите его в настройках браузера.')
  }
}

/** One capture at a time, kept outside React so it survives page navigation. */
class TabCapture {
  private state: CaptureState = { status: 'idle' }
  private listeners = new Set<Listener>()
  private streams: MediaStream[] = []
  private context: AudioContext | null = null
  private socket: WebSocket | null = null
  private stopped = true
  private retries = 0

  getState = (): CaptureState => this.state

  subscribe = (listener: Listener) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private set(state: CaptureState) {
    this.state = state
    this.listeners.forEach((listener) => listener())
  }

  async start(meetingId: string, streams: MediaStream[], withMic: boolean) {
    this.stop('Начата новая запись')
    this.stopped = false
    this.streams = streams
    this.context = new AudioContext({ sampleRate: 16000 })
    await this.context.audioWorklet.addModule('/pcm-worklet.js')
    const writer = new AudioWorkletNode(this.context, 'pcm-writer')
    for (const stream of streams) this.context.createMediaStreamSource(stream).connect(writer)
    const startedAt = Date.now()
    writer.port.onmessage = ({ data }: MessageEvent<{ pcm: ArrayBuffer; level: number }>) => {
      if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(data.pcm)
      if (this.state.status === 'streaming' || this.state.status === 'reconnecting') this.set({ ...this.state, level: data.level })
    }
    streams[0].getAudioTracks()[0].addEventListener('ended', () => this.stop('Показ вкладки остановлен'))
    this.set({ status: 'streaming', meetingId, level: 0, startedAt, withMic })
    await this.connect(meetingId)
  }

  private async connect(meetingId: string) {
    if (this.stopped) return
    try {
      const { ticket } = await sendJson<{ ticket: string }>(`/api/live/${meetingId}/ticket`, 'POST', { purpose: 'audio' })
      const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
      const socket = new WebSocket(`${scheme}://${location.host}/api/live/${meetingId}/audio?ticket=${encodeURIComponent(ticket)}`)
      socket.binaryType = 'arraybuffer'
      this.socket = socket
      socket.onopen = () => {
        this.retries = 0
        if (this.state.status === 'reconnecting') this.set({ ...this.state, status: 'streaming' })
      }
      socket.onmessage = ({ data }) => {
        if (typeof data === 'string' && JSON.parse(data).type === 'stopped') this.stop('Сессия завершена')
      }
      socket.onclose = (event) => {
        if (this.stopped || this.socket !== socket) return
        if (event.code === 4401 || event.code === 4404 || this.retries >= 5) return this.stop('Сервер закрыл соединение')
        this.retries += 1
        if (this.state.status === 'streaming') this.set({ ...this.state, status: 'reconnecting' })
        setTimeout(() => void this.connect(meetingId), 1000 * this.retries)
      }
    } catch {
      this.stop('Не удалось подключиться к серверу')
    }
  }

  stop(reason = 'Остановлено') {
    const meetingId = 'meetingId' in this.state ? this.state.meetingId : null
    this.stopped = true
    this.socket?.close()
    this.socket = null
    this.streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
    this.streams = []
    void this.context?.close()
    this.context = null
    if (meetingId && this.state.status !== 'ended') this.set({ status: 'ended', meetingId, reason })
  }
}

export const tabCapture = new TabCapture()
