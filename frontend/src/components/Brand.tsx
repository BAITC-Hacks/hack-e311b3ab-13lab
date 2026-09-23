import { clsx } from 'clsx'

export function Brand({ className }: { className?: string }) {
  return <span className={clsx('inline-flex items-center gap-2.5 text-xl font-extrabold tracking-tight', className)}><img src="/brand/mark.svg" width="34" height="34" alt="" /><span>HATTAMA<span className="opacity-60">.AI</span></span></span>
}
