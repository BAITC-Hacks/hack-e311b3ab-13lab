import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../test/fetch'
import { renderRoutes } from '../test/render'
import { AdminPage } from './AdminPage'

const pendingUser = { id: 'p1', email: 'new@example.kz', name: 'Новый сотрудник', role: 'participant', role_label: 'Участник', active: false, pending: true, last_login_at: null, created_at: '2026-09-23T10:00:00+00:00', permissions: [] }
const overview = {
  users: { total: 3, active: 2, pending: 1, disabled: 0, by_role: { admin: 1, secretary: 1, chair: 0, participant: 0, auditor: 0 } },
  meetings: { total: 1, by_status: { ready: 1 } },
  system: { database: 'postgresql', storage: 'minio', provider_configured: true, pdf_configured: true, diarization_configured: false, registration_mode: 'approval', migrations: [{ id: '0001_initial_schema', applied_at: '' }, { id: '0002_user_registration', applied_at: '' }] },
  pending_registrations: [pendingUser],
  recent_activity: [{ id: 1, at: '2026-09-23T10:00:00+00:00', user_id: 'p1', user_email: 'new@example.kz', action: 'user_registered', meeting_id: null, detail: {} }],
}

describe('AdminPage', () => {
  it('approves a registration with the chosen role', async () => {
    let approvedWith: unknown
    mockApi({
      'GET /api/admin/overview': { body: overview },
      'POST /api/admin/registrations/p1/approve': (init) => {
        approvedWith = JSON.parse(String(init?.body))
        return { body: { ...pendingUser, role: 'chair', active: true, pending: false } }
      },
    })
    renderRoutes([{ path: '/admin', element: <AdminPage /> }], '/admin')
    const queue = await screen.findByRole('region', { name: 'Заявки на регистрацию' })
    expect(within(queue).getByText('Новый сотрудник')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
    expect(screen.getByText('0002_user_registration')).toBeInTheDocument()
    await userEvent.selectOptions(within(queue).getByLabelText('Роль для Новый сотрудник'), 'chair')
    await userEvent.click(within(queue).getByRole('button', { name: /Одобрить/ }))
    expect(await screen.findByText(/получил доступ: Председатель/)).toBeInTheDocument()
    expect(approvedWith).toEqual({ role: 'chair' })
  })
})
