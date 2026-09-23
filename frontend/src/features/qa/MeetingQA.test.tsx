import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MeetingQA } from './MeetingQA'
import { demoQuestions } from './demo'

describe('Q&A preview', () => {
  it('shows a fixture answer and its source without calling an API', async () => {
    const fetchMock = vi.fn(); vi.stubGlobal('fetch',fetchMock)
    render(<MeetingQA context="meeting" />)
    expect(screen.getByText(/не ответы по текущему совещанию/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button',{name:demoQuestions[0]}))
    const log = screen.getByRole('log')
    expect(await within(log).findByText(/За обновлённый план запуска отвечает Айжан/)).toBeInTheDocument()
    await userEvent.click(within(log).getByText('Цитата · 02:14'))
    expect(within(log).getByText('Айжан, подготовьте обновлённый план запуска к 27 сентября.')).toBeVisible()
    expect(fetchMock).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button',{name:'Начать заново'}))
    expect(within(log).queryByText(demoQuestions[0])).not.toBeInTheDocument()
  })
  it('does not invent an answer to a custom question', async () => {
    render(<MeetingQA />)
    await userEvent.type(screen.getByLabelText('Вопрос ассистенту'),'Сколько денег у нашей компании?')
    await userEvent.click(screen.getByRole('button',{name:'Отправить вопрос'}))
    expect(await screen.findByText(/Ответы на произвольные вопросы появятся/)).toBeInTheDocument()
    expect(screen.queryByText(/Цитата ·/)).not.toBeInTheDocument()
  })
  it('keeps the question available after a client failure', async () => {
    const client={ask:vi.fn().mockRejectedValue(new Error('offline'))}
    render(<MeetingQA client={client} />)
    await userEvent.click(screen.getByRole('button',{name:demoQuestions[1]}))
    expect(await screen.findByRole('alert')).toHaveTextContent('попробуйте ещё раз')
    expect(screen.getByLabelText('Вопрос ассистенту')).toHaveValue(demoQuestions[1])
  })
})
