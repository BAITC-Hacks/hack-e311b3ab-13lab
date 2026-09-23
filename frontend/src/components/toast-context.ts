import { createContext, useContext } from 'react'

export type ToastTone = 'success' | 'error' | 'info'

export interface ToastApi {
  notify: (message: string, tone?: ToastTone) => void
}

export const ToastContext = createContext<ToastApi>({ notify: () => undefined })

export function useToast(): ToastApi {
  return useContext(ToastContext)
}
