import { afterEach, describe, expect, it, vi } from 'vitest'
import { CaptureError, pickMeetingTab } from './capture'

function stream(audioTracks: number) {
  const stop = vi.fn()
  const tracks = Array.from({ length: audioTracks + 1 }, () => ({ stop }))
  return { stream: { getAudioTracks: () => tracks.slice(0, audioTracks), getTracks: () => tracks } as unknown as MediaStream, stop }
}

describe('pickMeetingTab', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('explains how to share tab audio when none is shared', async () => {
    const { stream: display, stop } = stream(0)
    vi.stubGlobal('navigator', { mediaDevices: { getDisplayMedia: vi.fn().mockResolvedValue(display) } })
    await expect(pickMeetingTab(false)).rejects.toThrow(/Поделиться звуком вкладки/)
    expect(stop).toHaveBeenCalled()
  })

  it('mixes the microphone when asked', async () => {
    const { stream: display } = stream(1)
    const { stream: mic } = stream(1)
    const getUserMedia = vi.fn().mockResolvedValue(mic)
    vi.stubGlobal('navigator', { mediaDevices: { getDisplayMedia: vi.fn().mockResolvedValue(display), getUserMedia } })
    expect(await pickMeetingTab(true)).toEqual([display, mic])
    expect(getUserMedia).toHaveBeenCalledWith({ audio: { echoCancellation: true, noiseSuppression: true } })
  })

  it('reports a cancelled picker', async () => {
    vi.stubGlobal('navigator', { mediaDevices: { getDisplayMedia: vi.fn().mockRejectedValue(new DOMException('denied')) } })
    await expect(pickMeetingTab(false)).rejects.toBeInstanceOf(CaptureError)
  })
})
