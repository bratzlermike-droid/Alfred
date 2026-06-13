"""
Alfred's Calendar Manager
Google Calendar integration — view, create, and manage events.
Uses Google Calendar API with OAuth.
"""
import os
import datetime
import json
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDS_FILE = os.path.expanduser("~/alfred_google_credentials.json")
TOKEN_FILE = os.path.expanduser("~/alfred_google_token.json")

_service = None


def _get_service():
    """Get authenticated Google Calendar service."""
    global _service
    if _service:
        return _service

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_FILE):
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=8877)

        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    _service = build('calendar', 'v3', credentials=creds)
    return _service


def get_todays_events():
    """Get today's calendar events."""
    service = _get_service()
    if not service:
        return "Google Calendar not configured. Place credentials at " + CREDS_FILE

    now = datetime.datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
    end = now.replace(hour=23, minute=59, second=59).isoformat() + 'Z'

    events = service.events().list(
        calendarId='primary', timeMin=start, timeMax=end,
        singleEvents=True, orderBy='startTime', maxResults=10
    ).execute()

    items = events.get('items', [])
    if not items:
        return "No events on your calendar today, Sir."

    lines = "Today's calendar:\n"
    for event in items:
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        if 'T' in start_time:
            t = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            time_str = t.strftime("%I:%M %p")
        else:
            time_str = "All day"
        summary = event.get('summary', 'Untitled')
        lines += "  " + time_str + " — " + summary + "\n"
    return lines.strip()


def get_upcoming_events(days=7):
    """Get events for the next N days."""
    service = _get_service()
    if not service:
        return "Google Calendar not configured."

    now = datetime.datetime.utcnow()
    end = (now + datetime.timedelta(days=days))
    start_str = now.isoformat() + 'Z'
    end_str = end.isoformat() + 'Z'

    events = service.events().list(
        calendarId='primary', timeMin=start_str, timeMax=end_str,
        singleEvents=True, orderBy='startTime', maxResults=20
    ).execute()

    items = events.get('items', [])
    if not items:
        return "No upcoming events in the next " + str(days) + " days, Sir."

    lines = "Upcoming events:\n"
    current_date = ""
    for event in items:
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        if 'T' in start_time:
            t = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            date_str = t.strftime("%A %b %d")
            time_str = t.strftime("%I:%M %p")
        else:
            date_str = start_time
            time_str = "All day"

        if date_str != current_date:
            current_date = date_str
            lines += "  " + date_str + ":\n"

        summary = event.get('summary', 'Untitled')
        lines += "    " + time_str + " — " + summary + "\n"
    return lines.strip()


def get_tomorrows_events():
    """Get tomorrow's events."""
    service = _get_service()
    if not service:
        return "Google Calendar not configured."

    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    start = tomorrow.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
    end = tomorrow.replace(hour=23, minute=59, second=59).isoformat() + 'Z'

    events = service.events().list(
        calendarId='primary', timeMin=start, timeMax=end,
        singleEvents=True, orderBy='startTime', maxResults=10
    ).execute()

    items = events.get('items', [])
    if not items:
        return "Nothing on the calendar tomorrow, Sir."

    lines = "Tomorrow's schedule:\n"
    for event in items:
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        if 'T' in start_time:
            t = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            time_str = t.strftime("%I:%M %p")
        else:
            time_str = "All day"
        summary = event.get('summary', 'Untitled')
        lines += "  " + time_str + " — " + summary + "\n"
    return lines.strip()


def create_event(summary, date_str, time_str=None, duration_hours=1):
    """Create a calendar event."""
    service = _get_service()
    if not service:
        return "Google Calendar not configured."

    try:
        if time_str:
            start_dt = datetime.datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M")
            end_dt = start_dt + datetime.timedelta(hours=duration_hours)
            event = {
                'summary': summary,
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/Los_Angeles'},
                'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/Los_Angeles'},
            }
        else:
            event = {
                'summary': summary,
                'start': {'date': date_str},
                'end': {'date': date_str},
            }

        created = service.events().insert(calendarId='primary', body=event).execute()
        return "Event created: " + summary
    except Exception as e:
        return "Could not create event: " + str(e)


def get_next_event():
    """Get the very next upcoming event."""
    service = _get_service()
    if not service:
        return None

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events = service.events().list(
        calendarId='primary', timeMin=now,
        singleEvents=True, orderBy='startTime', maxResults=1
    ).execute()

    items = events.get('items', [])
    if items:
        event = items[0]
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'Untitled')
        if 'T' in start_time:
            t = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            return {"summary": summary, "time": t, "time_str": t.strftime("%I:%M %p")}
        return {"summary": summary, "time": None, "time_str": "today"}
    return None


# ── Intent Detection ──────────────────────────────────────────
def detect_calendar_command(message):
    """Detect calendar-related commands."""
    msg = message.lower().strip()

    # Today's events
    if any(w in msg for w in ["today's calendar", "todays calendar", "calendar today",
                               "events today", "my calendar", "whats on my calendar",
                               "what's on my calendar", "schedule today",
                               "do i have anything today"]):
        return ("today", None)

    # Tomorrow
    if any(w in msg for w in ["tomorrow's calendar", "tomorrows calendar",
                               "calendar tomorrow", "events tomorrow",
                               "schedule tomorrow", "do i have anything tomorrow"]):
        return ("tomorrow", None)

    # This week
    if any(w in msg for w in ["this week's calendar", "calendar this week",
                               "events this week", "upcoming events",
                               "whats coming up", "what's coming up",
                               "schedule this week"]):
        return ("upcoming", None)

    # Next event
    if any(w in msg for w in ["next event", "next meeting", "next appointment",
                               "whats next", "what's next on my calendar"]):
        return ("next", None)

    return (None, None)


def execute_calendar_command(action, args):
    """Execute a calendar command."""
    if action == "today":
        return get_todays_events()
    elif action == "tomorrow":
        return get_tomorrows_events()
    elif action == "upcoming":
        return get_upcoming_events(7)
    elif action == "next":
        event = get_next_event()
        if event:
            return "Next event: " + event["summary"] + " at " + event["time_str"]
        return "No upcoming events, Sir."
    return "Unknown calendar command"
