import type { ReactNode } from 'react'
import { Brand } from './Layout'

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="hidden flex-col justify-between bg-forest-900 p-12 text-forest-100 lg:flex">
        <Brand className="text-white" />
        <div>
          <p className="text-[11px] font-bold tracking-[0.2em] text-lime-300">МЕНЬШЕ РУТИНЫ. БОЛЬШЕ ЯСНОСТИ.</p>
          <h1 className="mt-5 text-5xl leading-tight font-bold tracking-tight text-white">
            Каждое решение.
            <br />
            <span className="text-lime-300">Под контролем.</span>
          </h1>
          <p className="mt-6 max-w-md leading-relaxed text-forest-200">Запись совещания превращается в протокол и поручения, которые можно проверить по исходной речи.</p>
        </div>
        <p className="text-xs text-forest-200">RU / KZ / MIX · HackAlem AI · 13Lab</p>
      </section>
      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-5">
          <div className="lg:hidden">
            <Brand className="text-forest-900" />
          </div>
          {children}
        </div>
      </section>
    </div>
  )
}
