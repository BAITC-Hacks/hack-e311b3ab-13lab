import { clsx } from 'clsx'
import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import type { MeetingStatus } from '../api/types'
import { STATUS_LABELS, statusTone, type Tone } from '../lib/labels'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: 'bg-lime-300 text-forest-900 hover:bg-lime-400 border-lime-300 font-semibold',
  secondary: 'bg-white text-forest-900 hover:bg-sand-100 border-sand-200',
  ghost: 'bg-transparent text-forest-800 hover:bg-sand-100 border-transparent',
  danger: 'bg-white text-red-700 hover:bg-red-50 border-red-200',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'sm' | 'md'; loading?: boolean; icon?: ReactNode }) {
  return (
    <button
      type="button"
      {...props}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        size === 'md' ? 'px-4 py-2.5 text-sm' : 'px-3 py-1.5 text-xs',
        BUTTON_STYLES[variant],
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx('rounded-2xl border border-sand-200 bg-white', className)}>{children}</div>
}

const TONE_STYLES: Record<Tone, string> = {
  neutral: 'bg-sand-100 text-ink-muted',
  progress: 'bg-sky-50 text-sky-800',
  review: 'bg-amber-50 text-amber-800',
  success: 'bg-lime-100 text-lime-700',
  danger: 'bg-red-50 text-red-700',
}

export function Badge({ tone = 'neutral', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={clsx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap', TONE_STYLES[tone], className)}>{children}</span>
}

export function StatusBadge({ status }: { status: MeetingStatus }) {
  const tone = statusTone(status)
  return (
    <Badge tone={tone}>
      {tone === 'progress' && <Loader2 className="size-3 animate-spin" aria-hidden />}
      {STATUS_LABELS[status]}
    </Badge>
  )
}

const CONTROL = 'mt-1.5 block w-full rounded-lg border border-sand-200 bg-white px-3 py-2.5 text-sm text-ink placeholder:text-ink-soft focus:border-forest-700 disabled:bg-sand-50 disabled:text-ink-muted'

export function Field({ label, hint, children, className }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <label className="block text-xs font-medium text-ink-muted">
        {label}
        {children}
      </label>
      {hint && <p className="mt-1 text-xs text-ink-soft">{hint}</p>}
    </div>
  )
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(CONTROL, className)} />
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={clsx(CONTROL, className)}>
      {children}
    </select>
  )
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={clsx(CONTROL, 'resize-y leading-relaxed', className)} />
}

export function Notice({ tone = 'warning', title, children }: { tone?: 'warning' | 'error' | 'info' | 'success'; title?: string; children: ReactNode }) {
  return (
    <div
      role={tone === 'error' ? 'alert' : undefined}
      className={clsx(
        'rounded-xl px-4 py-3 text-sm leading-relaxed',
        tone === 'warning' && 'bg-amber-50 text-amber-900',
        tone === 'error' && 'bg-red-50 text-red-800',
        tone === 'info' && 'bg-sand-100 text-ink',
        tone === 'success' && 'bg-lime-100 text-forest-900',
      )}
    >
      {title && <p className="font-semibold">{title}</p>}
      {children}
    </div>
  )
}

export function Spinner({ label = 'Загрузка…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-16 text-sm text-ink-muted" role="status">
      <Loader2 className="size-5 animate-spin" aria-hidden />
      {label}
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-sand-300 bg-white/60 px-6 py-14 text-center">
      {icon && <div className="mb-3 text-forest-700">{icon}</div>}
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-ink-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function PageHeader({ eyebrow, title, actions, children }: { eyebrow?: string; title: string; actions?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <p className="text-[11px] font-bold tracking-[0.18em] text-lime-700 uppercase">{eyebrow}</p>}
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-balance sm:text-4xl">{title}</h1>
        {children && <div className="mt-2 text-sm text-ink-muted">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}
