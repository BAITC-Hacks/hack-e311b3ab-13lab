import { act, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Meeting } from '../../api/types'
import { mockApi } from '../../test/fetch'
import { renderRoutes } from '../../test/render'
import { installFakeWebSocket } from '../../test/websocket'
import { LiveView } from './LiveView'

const meeting = {
  id: 'm1', title: 'Планёрка', meeting_date: '2026-09-23', status: 'live', created_at: '', updated_at: '', version: 3, error: null,
  created_by: 'u1', chair_id: null, participant_ids: [], approved_at: null, approved_by: null, people: {}, approvals: [],
  permissions: ['view', 'read', 'edit'], source: { type: 'bot', platform: 'google_meet' },
  live: { status: 'joining', connector: 'bot', platform: 'google_meet', started_at: new Date().toISOString(), bot_name: 'HATTAMA.AI Секретарь' },
  segments: [], participants_seen: [],
} as unknown as Meeting

describe('LiveView', () => {
  it('streams status, participants and transcript from the events socket', async () => {
    const sockets = installFakeWebSocket()
    mockApi({ 'POST /api/live/m1/ticket': { body: { ticket: 't1' } } })
    renderRoutes([{ path: '/', element: <LiveView meeting={meeting} /> }], '/')
    await waitFor(() => expect(sockets.instances).toHaveLength(1))
    const socket = sockets.instances[0]
    expect(socket.url).toContain('/api/live/m1/events?ticket=t1')
    act(() => {
      socket.emit({ type: 'snapshot', meeting })
      socket.emit({ type: 'status', status: 'live' })
      socket.emit({ type: 'participants', participants: [{ platform_id: 'p1', name: 'Дархан' }, { platform_id: 'p2', name: 'Айбек' }], present: ['p1', 'p2'] })
      socket.emit({ type: 'speaker', platform_id: 'p2', name: 'Айбек', at: 3 })
      socket.emit({ type: 'segments', segments: [{ id: 's1', text: 'Алия, презентацию подготовь до пятницы.', start: 12, end: 15, speaker: 'Айбек' }], lag_seconds: 2 })
    })
    expect(screen.getByRole('status')).toHaveTextContent('Идёт ИИ-расшифровка')
    expect(screen.getByText('Алия, презентацию подготовь до пятницы.')).toBeInTheDocument()
    expect(screen.getByText('Дархан')).toBeInTheDocument()
    expect(screen.getByText('говорит')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Завершить и подготовить протокол/ })).toBeInTheDocument()
  })
})
