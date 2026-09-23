import { describe, expect, it } from 'vitest'
import { detectPlatform } from './platform'

describe('detectPlatform', () => {
  it('recognises the three platforms', () => {
    expect(detectPlatform('https://meet.google.com/abc-defg-hij')).toBe('google_meet')
    expect(detectPlatform('https://teams.microsoft.com/l/meetup-join/19%3ameeting/0')).toBe('teams')
    expect(detectPlatform('https://us05web.zoom.us/j/123?pwd=x')).toBe('zoom')
  })

  it('rejects look-alikes and unsafe links', () => {
    for (const url of ['http://meet.google.com/abc-defg-hij', 'https://meet.google.com.evil.example/abc', 'https://user:p@meet.google.com/abc', 'https://notzoom.us/j/1', 'https://zoom.us/', 'not a url']) {
      expect(detectPlatform(url)).toBeNull()
    }
  })
})
