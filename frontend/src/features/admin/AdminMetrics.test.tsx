import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AdminOverview } from '../../api/types'
import { renderRoutes } from '../../test/render'
import { AdminMetrics } from './AdminMetrics'

const data: AdminOverview = {
  users: { total: 4, active: 3, pending: 1, disabled: 0, by_role: { admin: 1, secretary: 1, chair: 0, participant: 1, auditor: 0 } },
  meetings: { total: 5, by_status: { approved: 2, ready: 2, failed: 1 } },
  metrics: { timezone: 'Asia/Almaty', daily_uploads: Array.from({ length: 30 }, (_, index) => ({ date: new Date(Date.UTC(2026, 7, 25 + index)).toISOString().slice(0, 10), count: index === 0 ? 3 : index === 29 ? 2 : 0 })), actions: { total: 8, open: 3, in_progress: 1, done: 4, needs_review: 2 } },
  system: { database: 'sqlite', storage: 'local', provider_configured: true, pdf_configured: true, diarization_configured: true, registration_mode: 'approval', migrations: [] },
  pending_registrations: [], recent_activity: [],
}
function render(data: AdminOverview) { renderRoutes([{ path: '/admin', element: <AdminMetrics data={data} /> }], '/admin') }

describe('AdminMetrics', () => {
  it('switches only the upload chart period and shows real completion counts', async () => {
    render(data)
    expect(screen.getByRole('img', { name: '2 утверждено из 5 совещаний' })).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Доля выполненных поручений' })).toHaveAttribute('value', '4')
    expect(within(screen.getByRole('group', { name: 'Загрузки совещаний за 7 дней' })).getAllByRole('img')).toHaveLength(7)
    await userEvent.click(screen.getByRole('button', { name: '30 дней' }))
    expect(within(screen.getByRole('group', { name: 'Загрузки совещаний за 30 дней' })).getAllByRole('img')).toHaveLength(30)
    expect(screen.getByRole('button', { name: '30 дней' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('3 · 25 авг.')).toBeInTheDocument()
  })
  it('handles empty data without NaN or an invented approval percentage', () => {
    render({ ...data, meetings: { total: 0, by_status: {} }, metrics: { ...data.metrics!, daily_uploads: data.metrics!.daily_uploads.map(day => ({ ...day, count: 0 })), actions: { total: 0, open: 0, in_progress: 0, done: 0, needs_review: 0 } } })
    expect(screen.getByText('В этом периоде загрузок пока нет')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '0 утверждено из 0 совещаний' })).toHaveTextContent('—')
    expect(document.body.textContent).not.toMatch(/NaN|Infinity/)
  })
})
