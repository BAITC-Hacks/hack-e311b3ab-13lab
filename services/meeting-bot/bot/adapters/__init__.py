from bot.adapters.google_meet import GoogleMeetAdapter
from bot.adapters.teams import TeamsAdapter
from bot.adapters.zoom import ZoomAdapter

ADAPTERS = {"google_meet": GoogleMeetAdapter, "teams": TeamsAdapter, "zoom": ZoomAdapter}
