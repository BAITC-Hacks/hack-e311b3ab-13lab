import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../test/fetch'
import { renderRoutes } from '../test/render'
import { LoginPage } from './LoginPage'

const secretary = { id: 'u1', email: 'secretary@example.kz', name: 'Секретарь', role: 'secretary', role_label: 'Секретарь', active: true, pending: false, last_login_at: null, created_at: '', permissions: ['meetings:create'] }

function renderLogin() {
  return renderRoutes(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/', element: <p>Главная</p> },
      { path: '/admin', element: <p>Админ-панель</p> },
    ],
    '/login',
  )
}

async function submit(password: string) {
  await userEvent.type(screen.getByLabelText('Email'), 'secretary@example.kz')
  await userEvent.type(screen.getByLabelText('Пароль'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Войти' }))
}

describe('LoginPage', () => {
  it('shows the server error for wrong credentials', async () => {
    mockApi({ 'GET /api/auth/registration': { body: { mode: 'approval' } }, 'POST /api/auth/login': { status: 401, body: { detail: 'Неверный email или пароль' } } })
    renderLogin()
    await submit('wrong-password')
    expect(await screen.findByRole('alert')).toHaveTextContent('Неверный email или пароль')
  })

  it('stores the session and opens the app', async () => {
    mockApi({ 'GET /api/auth/registration': { body: { mode: 'closed' } }, 'POST /api/auth/login': { body: { token: 'fresh-token', expires_at: 0, user: secretary } } })
    renderLogin()
    await submit('correct-password')
    expect(await screen.findByText('Главная')).toBeInTheDocument()
    expect(sessionStorage.getItem('hattama-token')).toBe('fresh-token')
  })

  it('sends administrators to the admin panel and links to registration', async () => {
    mockApi({ 'GET /api/auth/registration': { body: { mode: 'approval' } }, 'POST /api/auth/login': { body: { token: 't', expires_at: 0, user: { ...secretary, role: 'admin' } } } })
    renderLogin()
    expect(await screen.findByRole('link', { name: 'Зарегистрироваться' })).toHaveAttribute('href', '/register')
    await submit('correct-password')
    expect(await screen.findByText('Админ-панель')).toBeInTheDocument()
  })
})
