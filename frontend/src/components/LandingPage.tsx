import { useState, type ReactNode } from 'react'
import { ArrowDown, ArrowRight, Check, FileText, Headphones, Quote, ShieldCheck } from 'lucide-react'
import { Brand } from './Brand'
import { Integrations } from './Integrations'
import { MeetingQA } from '../features/qa/MeetingQA'

const sampleActions = [
  { title: 'Подготовить обновлённый план запуска', owner: 'Айжан', date: '27 сентября', quote: 'Айжан, подготовьте обновлённый план запуска к 27 сентября.', time: '02:14' },
  { title: 'Согласовать бюджет с финансовым отделом', owner: 'Тимур', date: '30 сентября', quote: 'Тимур, согласуйте бюджет с финансовым отделом до 30 сентября.', time: '04:38' },
]

export function LandingPage({ children }: { children: ReactNode }) {
  const [sample, setSample] = useState<'summary' | 'actions'>('actions')
  const [source, setSource] = useState<number | null>(null)
  return <div className="landing-page" id="top">
    <header className="landing-nav"><a href="#top" aria-label="HATTAMA.AI — главная"><Brand /></a><nav aria-label="О продукте"><a href="#example">Примеры</a><a href="#integrations">Интеграции</a><a href="#questions">Q&A</a><a href="#sign-in" className="landing-login-link">Войти <ArrowRight className="size-4" /></a></nav></header>
    <main>
      <section className="landing-hero">
        <div className="hero-story"><p className="brand-eyebrow"><span /> ИЗ РАЗГОВОРА — В ДЕЙСТВИЕ</p><h1>Совещание закончилось.<br /><span>Ясность осталась.</span></h1><p className="hero-description">Кто, что и к какому сроку. Превратите запись встречи в понятный протокол — с поручениями, исполнителями и ссылками на исходную речь.</p><a className="example-link" href="#example">Посмотреть, как это работает <ArrowDown className="size-4" /></a><div className="hero-art"><img src="/brand/conversation-to-protocol.png" alt="Звуковая волна превращается в листы протокола с отметкой выполнения" width="1536" height="1024" /><span className="hero-art-caption"><Headphones className="size-3.5" /> Разговор → проверяемый протокол</span></div></div>
        <aside id="sign-in" className="sign-in-card"><span className="sign-in-eyebrow">ВАШЕ РАБОЧЕЕ ПРОСТРАНСТВО</span>{children}<p className="admin-login-note"><ShieldCheck className="size-4 shrink-0" /><span>Для администратора — тот же вход. Панель управления откроется по роли учётной записи.</span></p></aside>
      </section>
      <Integrations />
      <section className="how-it-works" aria-label="Как это работает">{[{n:'01',title:'Загрузите запись',text:'Аудио встречи на русском, казахском или двух языках.'},{n:'02',title:'Проверьте главное',text:'Уточните имена, сроки и цитаты в одном рабочем пространстве.'},{n:'03',title:'Утвердите протокол',text:'Скачайте документ и передайте поручения исполнителям.'}].map(step => <div key={step.n}><span>{step.n}</span><div><h2>{step.title}</h2><p>{step.text}</p></div></div>)}</section>
      <section id="example" className="landing-example">
        <div className="example-intro"><p className="brand-eyebrow">ПРОТОКОЛ, КОТОРЫЙ МОЖНО ПРОВЕРИТЬ</p><h2>Не теряйте решения<br />среди реплик.</h2><p>Откройте поручение и посмотрите, на чём оно основано. В рабочем протоколе от цитаты можно перейти к нужной секунде записи.</p><span className="demo-label">Демонстрационный пример · вымышленные данные</span></div>
        <div className="demo-protocol"><div className="demo-heading"><span className="demo-icon"><FileText className="size-5" /></span><div><p>Планирование запуска</p><span>23 сентября · 3 участника</span></div><span className="demo-draft">Черновик</span></div><div className="demo-tabs"><button type="button" aria-pressed={sample==='summary'} onClick={() => setSample('summary')}>Краткое содержание</button><button type="button" aria-pressed={sample==='actions'} onClick={() => setSample('actions')}>Поручения <span>2</span></button></div>{sample==='summary' ? <div className="demo-summary"><h3>Запуск — после проверки плана и бюджета</h3><p>Команда обсудила подготовку к запуску. Решили обновить план и согласовать бюджет с финансовым отделом.</p><p className="mt-4 flex items-center gap-2 text-sm"><Check className="size-4" /> Два следующих шага закреплены за исполнителями.</p></div> : <div className="demo-actions">{sampleActions.map((action,i) => <div key={action.title}><h3><span>{String(i+1).padStart(2,'0')}</span>{action.title}</h3><div className="demo-action-meta"><span>{action.owner}</span><span>{action.date}</span><button type="button" aria-expanded={source===i} onClick={() => setSource(source===i ? null : i)}><Quote className="size-3.5" />{source===i ? 'Скрыть цитату' : 'Показать цитату'}</button></div>{source===i && <blockquote><span>{action.time}</span> «{action.quote}»</blockquote>}</div>)}</div>}<div className="demo-footer"><ShieldCheck className="size-4" /> Финальное решение остаётся за человеком</div></div>
      </section>
      <section id="questions" className="qa-showcase"><div className="example-intro"><p className="brand-eyebrow">СЛЕДУЮЩИЙ ШАГ · Q&A</p><h2>Спросите о главном.<br />Вернитесь к источнику.</h2><p>Будущий ассистент поможет находить ответы по встрече. Уже сейчас можно попробовать интерфейс: выбрать вопрос, прочитать ответ и раскрыть подтверждающую цитату.</p><ul className="qa-benefits"><li><Check size={15} /> Вопросы обычным языком</li><li><Check size={15} /> Ответы с указанием источника</li><li><Check size={15} /> Поручения, решения и сроки</li></ul><span className="demo-label">Сейчас — интерактивное демо. Подключение к данным встречи в разработке.</span></div><MeetingQA /></section>
      <section className="landing-faq" id="faq"><div><p className="brand-eyebrow">ПЕРЕД ПЕРВОЙ ВСТРЕЧЕЙ</p><h2>Коротко о важном.</h2></div><div>{[
        ['Что уже можно попробовать?', 'Загрузку записи, расшифровку с говорящими при подключённой диаризации, проверку поручений, утверждение и экспорт протокола.'],
        ['Zoom и Teams уже подключены?', 'Пока нет. Карточки показывают запланированные интеграции. Сейчас используйте ручную загрузку сохранённой записи.'],
        ['Q&A отвечает по моему совещанию?', 'Ещё нет. Демо использует вымышленную встречу и готовые ответы. Оно не читает ваши протоколы и не отправляет вопросы языковой модели.'],
        ['Кто проверяет результат?', 'Секретарь или председатель сверяет цитаты, имена и сроки, вносит правки и утверждает протокол. ИИ готовит черновик.'],
      ].map(([question,answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div></section>
      <section className="landing-bottom"><Brand className="text-white" /><p>Меньше времени на протокол.<br /><strong>Больше внимания решениям.</strong></p><a href="#sign-in">Войти в рабочее пространство <ArrowRight className="size-4" /></a></section>
    </main>
    <footer className="landing-footer"><span>HATTAMA.AI · 13Lab</span><span>Русский · Қазақша · Смешанная речь</span><a href="#sign-in">Вход для администратора</a></footer>
  </div>
}
