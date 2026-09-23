import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LandingPage } from './LandingPage'

describe('Public meeting example', () => {
  it('shows a clearly marked synthetic example without fetching private meetings', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch',fetchMock)
    render(<LandingPage><p>Форма входа</p></LandingPage>)
    expect(screen.getByText(/вымышленные данные/)).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button',{name:'Показать цитату'})[0])
    expect(screen.getByText(/«Айжан, подготовьте/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button',{name:'Краткое содержание'}))
    expect(screen.getByText('Запуск — после проверки плана и бюджета')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByRole('link',{name:'Вход для администратора'})).toHaveAttribute('href','#sign-in')
  })
})
