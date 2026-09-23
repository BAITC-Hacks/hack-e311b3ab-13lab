import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthProvider'
import { LoginPage } from './LoginPage'

function renderLogin() {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/', element: <p>Главная</p> },
    ],
    { initialEntries: ['/login'] },
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('LoginPage', () => {
  it('shows the server error for wrong credentials', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { detail: 'Неверный email или пароль' })))
    renderLogin()
    await userEvent.type(screen.getByLabelText('Email'), 'secretary@example.kz')
    await userEvent.type(screen.getByLabelText('Пароль'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Неверный email или пароль')
  })

  it('stores the session and opens the app', async () => {
    const user = { id: 'u1', email: 'secretary@example.kz', name: 'Секретарь', role: 'secretary', role_label: 'Секретарь', active: true, created_at: '', permissions: ['meetings:create'] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, { token: 'fresh-token', expires_at: 0, user })))
    renderLogin()
    await userEvent.type(screen.getByLabelText('Email'), 'secretary@example.kz')
    await userEvent.type(screen.getByLabelText('Пароль'), 'correct-password')
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByText('Главная')).toBeInTheDocument()
    expect(sessionStorage.getItem('hattama-token')).toBe('fresh-token')
  })
})
