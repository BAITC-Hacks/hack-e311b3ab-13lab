import { useSyncExternalStore } from 'react'
import { tabCapture } from './capture'

export function useCaptureState() {
  return useSyncExternalStore(tabCapture.subscribe, tabCapture.getState)
}
