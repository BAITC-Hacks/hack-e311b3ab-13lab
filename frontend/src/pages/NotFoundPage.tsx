import { Link } from 'react-router'
import { EmptyState } from '../components/ui'

export function NotFoundPage() {
  return (
    <EmptyState title="Страница не найдена" action={<Link to="/" className="text-sm font-semibold text-forest-800 underline">К списку совещаний</Link>}>
      Проверьте адрес или вернитесь к списку совещаний.
    </EmptyState>
  )
}
