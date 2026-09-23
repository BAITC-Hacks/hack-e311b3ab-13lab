import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom does not implement scrolling; every real browser does.
Element.prototype.scrollIntoView = () => undefined

afterEach(() => {
  cleanup()
  sessionStorage.clear()
})
