/** Mirrors backend/app/integrations/registry.py for instant feedback; the server re-checks. */
export function detectPlatform(url: string): string | null {
  try {
    const parsed = new URL(url.trim())
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || (parsed.port && parsed.port !== '443')) return null
    const host = parsed.hostname.toLowerCase()
    const matches = (domain: string) => host === domain || host.endsWith(`.${domain}`)
    if (host === 'meet.google.com' && parsed.pathname.replace(/\//g, '').length >= 3) return 'google_meet'
    if ((matches('teams.microsoft.com') || matches('teams.live.com')) && parsed.pathname !== '/') return 'teams'
    if (matches('zoom.us') && /\/(j|wc|my)\//.test(parsed.pathname)) return 'zoom'
  } catch {
    return null
  }
  return null
}
