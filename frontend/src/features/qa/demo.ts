/** Frontend-only fixtures. No real meeting or network request is used. */
export interface QASource { id: string; time: string; quote: string }
export interface QAAnswer { text: string; sources: QASource[] }
export interface QAClient { ask(question: string, signal?: AbortSignal): Promise<QAAnswer> }

export const demoQuestions = ['Кто отвечает за план запуска?', 'Какие сроки согласовали?', 'Что решили на встрече?']
export const demoSources: QASource[] = [
  { id: 'plan', time: '02:14', quote: 'Айжан, подготовьте обновлённый план запуска к 27 сентября.' },
  { id: 'budget', time: '04:38', quote: 'Тимур, согласуйте бюджет с финансовым отделом до 30 сентября.' },
]
const answers: QAAnswer[] = [
  { text: 'За обновлённый план запуска отвечает Айжан. Согласованный срок — 27 сентября.', sources: [demoSources[0]] },
  { text: 'В примере согласованы два срока:\n• 27 сентября — обновлённый план запуска, Айжан.\n• 30 сентября — согласование бюджета, Тимур.', sources: demoSources },
  { text: 'Обновить план запуска и согласовать бюджет с финансовым отделом. Поручения закреплены за Айжан и Тимуром.', sources: demoSources },
]
export const demoQAClient: QAClient = {
  async ask(question) {
    const index = demoQuestions.findIndex((item) => item.toLocaleLowerCase().replace(/[?!.]/g, '') === question.trim().toLocaleLowerCase().replace(/[?!.]/g, ''))
    return index >= 0 ? structuredClone(answers[index]) : {
      text: 'Это демонстрация интерфейса с готовыми ответами. Ответы на произвольные вопросы появятся после подключения Q&A. Пока выберите один из примеров ниже.', sources: [],
    }
  },
}
