import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Integrations } from './Integrations'

describe('Upcoming integrations', () => {
  it('explains Zoom availability and offers manual upload without OAuth', async () => {
    const fetchMock=vi.fn(); vi.stubGlobal('fetch',fetchMock)
    render(<Integrations />)
    await userEvent.click(screen.getByRole('button',{name:/Zoom Онлайн-встречи Скоро/}))
    expect(screen.getByRole('region',{name:'Подробнее: Zoom'})).toHaveTextContent('автоматическое подключение ещё недоступно')
    expect(screen.getByRole('link',{name:'Пока можно загрузить запись'})).toHaveAttribute('href','#sign-in')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
