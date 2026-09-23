import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowUp, MessageCircle, RotateCcw, Quote, Sparkles } from 'lucide-react'
import { demoQAClient, demoQuestions, type QAAnswer, type QAClient } from './demo'

type Message = { id: number; role: 'user'; text: string } | { id: number; role: 'assistant'; answer: QAAnswer }

/** Replace the client when the teammate adds retrieval. Keep source citations in the contract. */
export function MeetingQA({ context = 'public', client = demoQAClient }: { context?: 'public' | 'meeting'; client?: QAClient }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  const log = useRef<HTMLDivElement>(null)
  const sequence = useRef(0)
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    const node = log.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages, pending])

  async function ask(value: string) {
    const text = value.trim()
    if (!text || pending) return
    setQuestion('')
    setError('')
    setPending(true)
    setMessages((current) => [...current.slice(-18), { id: ++sequence.current, role: 'user', text }])
    const request = new AbortController()
    controller.current = request
    try {
      const answer = await client.ask(text, request.signal)
      if (!request.signal.aborted) setMessages((current) => [...current, { id: ++sequence.current, role: 'assistant', answer }])
    } catch {
      if (!request.signal.aborted) { setError('Не удалось получить ответ. Вопрос сохранён в поле — попробуйте ещё раз.'); setQuestion(text) }
    } finally {
      if (!request.signal.aborted) setPending(false)
    }
  }
  function submit(event: FormEvent) { event.preventDefault(); void ask(question) }

  return <section className="qa-panel" aria-label="Демонстрационный Q&A">
    <header className="qa-header"><span className="qa-avatar"><Sparkles size={18} /></span><div><h3>Спросите HATTAMA</h3><p>Пример: «Планирование запуска»</p></div><span className="feature-soon">Демо · скоро</span></header>
    <p className="qa-disclaimer">{context === 'meeting' ? 'Это вымышленный пример, а не ответы по текущему совещанию. Q&A ещё не подключён.' : 'Вымышленная встреча и готовые ответы. Полноценный Q&A появится позже.'}</p>
    <div className="qa-log" ref={log} role="log" aria-label="Переписка с демонстрационным ассистентом" aria-live="polite" aria-relevant="additions">
      {!messages.length && <div className="qa-welcome"><MessageCircle size={28} strokeWidth={1.4} /><h4>Один вопрос вместо<br />долгого поиска.</h4><p>Кто отвечает за задачу? Какой срок? Попробуйте вопрос — и откройте цитату в ответе.</p></div>}
      {messages.map((message) => message.role === 'user' ? <div className="qa-user" key={message.id}><span className="sr-only">Ваш вопрос: </span>{message.text}</div> : <div className="qa-answer" key={message.id}><span className="qa-answer-label"><Sparkles size={12} /> HATTAMA · демонстрационный ответ</span><p>{message.answer.text}</p>{message.answer.sources.length > 0 && <div className="qa-sources"><span>На основании реплик примера</span>{message.answer.sources.map((source) => <details key={source.id}><summary><Quote size={12} /> Цитата · {source.time}</summary><blockquote>{source.quote}</blockquote></details>)}</div>}</div>)}
      {pending && <p className="qa-pending" role="status">Готовим ответ…</p>}
    </div>
    <div className="qa-suggestions" aria-label="Примеры вопросов">{demoQuestions.map((text) => <button type="button" key={text} disabled={pending} onClick={() => void ask(text)}>{text}</button>)}</div>
    {error && <p className="qa-error" role="alert">{error}</p>}
    <form className="qa-composer" onSubmit={submit}><label className="sr-only" htmlFor={`qa-question-${context}`}>Вопрос ассистенту</label><input id={`qa-question-${context}`} maxLength={1000} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Задайте вопрос или выберите пример" autoComplete="off" /><button type="submit" aria-label="Отправить вопрос" disabled={!question.trim() || pending}><ArrowUp size={18} /></button></form>
    <footer className="qa-footer"><span>Ответы можно проверить по цитатам</span>{messages.length > 0 && <button type="button" disabled={pending} onClick={() => { setMessages([]); setError(''); setQuestion('') }}><RotateCcw size={12} /> Начать заново</button>}</footer>
  </section>
}
