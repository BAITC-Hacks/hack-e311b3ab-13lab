import { useEffect, useRef, type ReactNode } from 'react'
import { Button } from './ui'

export function Dialog({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      aria-label={title}
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-2xl border border-sand-200 bg-white p-6 text-ink shadow-xl"
    >
      {open && (
        <>
          <h2 className="mb-4 text-lg font-semibold">{title}</h2>
          {children}
        </>
      )}
    </dialog>
  )
}

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  danger = false,
  loading = false,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  children: ReactNode
  confirmLabel: string
  danger?: boolean
  loading?: boolean
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <div className="text-sm leading-relaxed text-ink-muted">{children}</div>
      <div className="mt-6 flex justify-end gap-2">
        <Button onClick={onClose}>Отмена</Button>
        <Button variant={danger ? 'danger' : 'primary'} loading={loading} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  )
}
