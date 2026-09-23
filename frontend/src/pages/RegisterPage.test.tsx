import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../test/fetch'
import { renderRoutes } from '../test/render'
import { RegisterPage } from './RegisterPage'

async function fill(password: string, confirm = password) {
  await userEvent.type(await screen.findByLabelText('Имя и фамилия'), 'Айжан Серикова')
  await userEvent.type(screen.getByLabelText('Email'), 'aizhan@example.kz')
  await userEvent.type(screen.getByLabelText('Пароль'), password)
  await userEvent.type(screen.getByLabelText('Повторите пароль'), confirm)
  await userEvent.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))
}

describe('RegisterPage', () => {
  it('explains that the request waits for an administrator', async () => {
    const fetchMock = mockApi({ 'GET /api/auth/registration': { body: { mode: 'approval' } }, 'POST /api/auth/register': { status: 201, body: { status: 'pending' } } })
    renderRoutes([{ path: '/register', element: <RegisterPage /> }], '/register')
    await fill('long-enough-password')
    expect(await screen.findByText('Заявка отправлена')).toBeInTheDocument()
    const body = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === '/api/auth/register')?.[1]?.body))
    expect(body).toEqual({ name: 'Айжан Серикова', email: 'aizhan@example.kz', password: 'long-enough-password' })
  })

  it('checks that passwords match before sending', async () => {
    const fetchMock = mockApi({ 'GET /api/auth/registration': { body: { mode: 'open' } } })
    renderRoutes([{ path: '/register', element: <RegisterPage /> }], '/register')
    await fill('long-enough-password', 'different-password')
    expect(await screen.findByText('Пароли не совпадают')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/auth/register')).toBe(false)
  })

  it('shows that registration is closed', async () => {
    mockApi({ 'GET /api/auth/registration': { body: { mode: 'closed' } } })
    renderRoutes([{ path: '/register', element: <RegisterPage /> }], '/register')
    expect(await screen.findByText('Регистрация закрыта')).toBeInTheDocument()
  })
})
