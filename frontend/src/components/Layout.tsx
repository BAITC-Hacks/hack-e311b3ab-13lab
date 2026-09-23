import { clsx } from 'clsx'
import { ClipboardList, FilePlus2, KeyRound, LayoutDashboard, LogOut, Menu, ScrollText, Users, Video, X } from 'lucide-react'
import { useState, type ComponentType } from 'react'
import { NavLink, Outlet } from 'react-router'
import { useHealth } from '../api/queries'
import type { GlobalPermission } from '../api/types'
import { useAuth } from '../auth/context'
import { Brand } from './Brand'
import { PasswordDialog } from './PasswordDialog'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  permission?: GlobalPermission
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/admin', label: 'Админ-панель', icon: LayoutDashboard, permission: 'users:manage' },
  { to: '/', label: 'Совещания', icon: Video, end: true },
  { to: '/meetings/new', label: 'Новое совещание', icon: FilePlus2, permission: 'meetings:create' },
  { to: '/tasks', label: 'Мои поручения', icon: ClipboardList },
  { to: '/users', label: 'Пользователи', icon: Users, permission: 'users:manage' },
  { to: '/audit', label: 'Журнал действий', icon: ScrollText, permission: 'audit:read' },
]

export { Brand } from './Brand'

export function Layout() {
  const { user, can, logout } = useAuth()
  const health = useHealth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [passwordOpen, setPasswordOpen] = useState(false)
  const items = NAV.filter((item) => !item.permission || can(item.permission))

  return (
    <div className="min-h-screen lg:flex">
      <aside className={clsx('bg-forest-900 text-forest-100 lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col', menuOpen ? 'flex flex-col' : 'flex')}>
        <div className="flex w-full items-center justify-between px-5 py-4 lg:block lg:px-6 lg:pt-8 lg:pb-0">
          <NavLink to="/" className="text-white" onClick={() => setMenuOpen(false)}>
            <Brand />
          </NavLink>
          <p className="mt-2 hidden text-[10px] font-semibold tracking-[0.2em] text-forest-200 lg:block">ПРОТОКОЛЫ И ПОРУЧЕНИЯ</p>
          <button type="button" className="rounded-lg p-2 text-forest-100 hover:bg-forest-800 lg:hidden" onClick={() => setMenuOpen((open) => !open)} aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={menuOpen}>
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
        <div className={clsx('flex-1 flex-col px-3 pb-5 lg:mt-8 lg:flex', menuOpen ? 'flex' : 'hidden')}>
          <nav className="space-y-1" aria-label="Разделы">
            {items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) => clsx('flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors', isActive ? 'bg-forest-700 text-white' : 'text-forest-100 hover:bg-forest-800')}
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto border-t border-forest-800 pt-4">
            <div className="px-3">
              <p className="truncate text-sm font-semibold text-white">{user?.name}</p>
              <p className="truncate text-xs text-forest-200">
                {user?.role_label} · {user?.email}
              </p>
            </div>
            <div className="mt-3 flex gap-1">
              <button type="button" onClick={() => setPasswordOpen(true)} className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-xs text-forest-100 hover:bg-forest-800">
                <KeyRound className="size-4" /> Пароль
              </button>
              <button type="button" onClick={() => void logout()} className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-xs text-forest-100 hover:bg-forest-800">
                <LogOut className="size-4" /> Выйти
              </button>
            </div>
          </div>
        </div>
      </aside>
      <div className="min-w-0 flex-1 lg:ml-64">
        <header className="flex h-12 items-center justify-end border-b border-sand-200 px-4 sm:px-8">
          {health.data && (
            <span className={clsx('rounded-full px-3 py-1.5 text-xs', health.data.provider_configured ? 'bg-lime-100 text-lime-700' : 'bg-amber-50 text-amber-800')}>
              {health.data.provider_configured ? '● Готово к работе' : '○ Ключ сервиса моделей не задан'}
            </span>
          )}
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-8 sm:py-7">
          <Outlet />
        </main>
      </div>
      <PasswordDialog open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </div>
  )
}
