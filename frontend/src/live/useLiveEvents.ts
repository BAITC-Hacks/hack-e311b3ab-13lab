import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { sendJson } from '../api/client'
import { queryKeys } from '../api/queries'
import type { LiveEvent, Meeting, Segment } from '../api/types'

export interface LiveView {
  connected: boolean
  status: string
  detail: string
  segments: Segment[]
  participants: Array<{ platform_id: string; name: string; present: boolean }>
  speaking: string | null
  warnings: string[]
  lag: number
}

const INITIAL: LiveView = { connected: false, status: 'joining', detail: '', segments: [], participants: [], speaking: null, warnings: [], lag: 0 }

/** Live transcript and status over the events WebSocket, reconnecting until the session ends. */
export function useLiveEvents(meetingId: string, enabled: boolean): LiveView {
  const queryClient = useQueryClient()
  const [view, setView] = useState<LiveView>(INITIAL)

  useEffect(() => {
    if (!enabled) return
    let socket: WebSocket | null = null
    let finished = false
    let attempts = 0
    let timer: ReturnType<typeof setTimeout> | undefined

    function apply(event: LiveEvent) {
      setView((current) => {
        switch (event.type) {
          case 'snapshot': {
            const meeting = event.meeting as Meeting
            return {
              ...current,
              connected: true,
              status: meeting.live?.status ?? current.status,
              detail: meeting.live?.detail ?? '',
              segments: meeting.segments ?? [],
              participants: (meeting.participants_seen ?? []).map((item) => ({ ...item, present: true })),
            }
          }
          case 'segments':
            return { ...current, segments: [...current.segments, ...event.segments.map((segment, index) => ({ ...segment, id: `live-${current.segments.length + index}` }))], lag: event.lag_seconds ?? 0 }
          case 'status':
            return { ...current, status: event.status, detail: event.detail ?? '' }
          case 'participants':
            return { ...current, participants: event.participants.map((item) => ({ ...item, present: event.present.includes(item.platform_id) })) }
          case 'speaker':
            return { ...current, speaking: event.name }
          case 'warning':
            return { ...current, warnings: [...current.warnings.slice(-4), event.message] }
          default:
            return current
        }
      })
    }

    async function connect() {
      try {
        const { ticket } = await sendJson<{ ticket: string }>(`/api/live/${meetingId}/ticket`, 'POST', { purpose: 'events' })
        const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
        socket = new WebSocket(`${scheme}://${location.host}/api/live/${meetingId}/events?ticket=${encodeURIComponent(ticket)}`)
        socket.onopen = () => {
          attempts = 0
        }
        socket.onmessage = ({ data }) => {
          const event = JSON.parse(String(data)) as LiveEvent
          if (event.type === 'finished') {
            finished = true
            void queryClient.invalidateQueries({ queryKey: queryKeys.meeting(meetingId) })
            void queryClient.invalidateQueries({ queryKey: queryKeys.meetings })
          }
          apply(event)
        }
        socket.onclose = () => {
          setView((current) => ({ ...current, connected: false }))
          if (!finished && attempts < 10) {
            attempts += 1
            timer = setTimeout(() => void connect(), Math.min(10000, 1000 * attempts))
          }
        }
      } catch {
        if (!finished && attempts < 10) {
          attempts += 1
          timer = setTimeout(() => void connect(), Math.min(10000, 1000 * attempts))
        }
      }
    }

    void connect()
    return () => {
      finished = true
      clearTimeout(timer)
      socket?.close()
    }
  }, [meetingId, enabled, queryClient])

  return view
}
