"""Meeting links the bot may open. Anything else is rejected, so the bot can never be
pointed at internal addresses or arbitrary sites."""

from urllib.parse import urlsplit

PLATFORMS = {
    "google_meet": "Google Meet",
    "teams": "Microsoft Teams",
    "zoom": "Zoom",
}


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def detect_platform(url: str) -> str | None:
    """Return the platform id for an allowed meeting link, or None."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        return None
    host = parts.hostname.lower()
    path = parts.path or "/"
    if host == "meet.google.com" and len(path.strip("/")) >= 3:
        return "google_meet"
    if (_host_matches(host, "teams.microsoft.com") or _host_matches(host, "teams.live.com")) and path != "/":
        return "teams"
    if _host_matches(host, "zoom.us") and ("/j/" in path or "/wc/" in path or "/my/" in path):
        return "zoom"
    return None
