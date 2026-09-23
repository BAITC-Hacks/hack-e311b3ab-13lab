import { CheckCircle2, Info, TriangleAlert, X } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { clsx } from 'clsx'
import { ToastContext, type ToastTone } from './toast-context'

interface Toast {
  id: number
  message: string
  tone: ToastTone
}

const ICONS = { success: CheckCircle2, error: TriangleAlert, info: Info }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((items) => items.filter((item) => item.id !== id)), [])

  const notify = useCallback(
    (message: string, tone: ToastTone = 'success') => {
      const id = nextId.current++
      setToasts((items) => [...items.slice(-3), { id, message, tone }])
      setTimeout(() => dismiss(id), tone === 'error' ? 8000 : 4000)
    },
    [dismiss],
  )

  const api = useMemo(() => ({ notify }), [notify])
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:left-auto" aria-live="polite">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.tone]
          return (
            <div
              key={toast.id}
              role={toast.tone === 'error' ? 'alert' : 'status'}
              className={clsx(
                'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg',
                toast.tone === 'success' && 'border-lime-200 bg-white text-forest-900',
                toast.tone === 'error' && 'border-red-200 bg-red-50 text-red-900',
                toast.tone === 'info' && 'border-sand-200 bg-white text-ink',
              )}
            >
              <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span className="flex-1">{toast.message}</span>
              <button type="button" onClick={() => dismiss(toast.id)} className="text-ink-muted hover:text-ink" aria-label="Закрыть уведомление">
                <X className="size-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
