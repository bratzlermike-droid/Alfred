"""
Alfred's Daily Briefing System
Gathers weather, news, reminders, and delivers a morning report.
"""
import json
import os
import datetime
import requests

REMINDERS_FILE = os.path.expanduser("~/alfred_reminders.json")
WEATHER_CITY = "Reno+Nevada"
GROQ_CONFIG = os.path.expanduser("~/chief_config.txt")
SERVER_URL = os.environ.get("ALFRED_SERVER_URL", "http://localhost:8000")
AUTH_TOKEN = "Bearer " + os.environ.get("ALFRED_AUTH_TOKEN", "change-me-in-env")


def _load_reminders():
    """Load reminders from local file."""
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r') as f:
            return json.load(f)
    return []


def _save_reminders(reminders):
    """Save reminders to local file."""
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(reminders, f, indent=2)


def add_reminder(text, date=None):
    """Add a reminder. Date is optional (defaults to today)."""
    reminders = _load_reminders()
    if date is None:
        date = datetime.date.today().isoformat()
    reminders.append({
        "text": text,
        "date": date,
        "created": datetime.datetime.now().isoformat(),
        "done": False
    })
    _save_reminders(reminders)
    return "Reminder added: " + text


def get_todays_reminders():
    """Get reminders for today and overdue."""
    reminders = _load_reminders()
    today = datetime.date.today().isoformat()
    active = []
    for r in reminders:
        if not r["done"] and r["date"] <= today:
            active.append(r["text"])
    return active


def complete_reminder(text):
    """Mark a reminder as done."""
    reminders = _load_reminders()
    for r in reminders:
        if text.lower() in r["text"].lower() and not r["done"]:
            r["done"] = True
            _save_reminders(reminders)
            return "Reminder completed: " + r["text"]
    return "Reminder not found"


def clear_done_reminders():
    """Remove completed reminders."""
    reminders = _load_reminders()
    reminders = [r for r in reminders if not r["done"]]
    _save_reminders(reminders)
    return "Cleared completed reminders"


def get_weather():
    """Get current weather using wttr.in (free, no API key needed)."""
    try:
        r = requests.get(
            "https://wttr.in/" + WEATHER_CITY + "?format=j1",
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            current = data["current_condition"][0]
            temp_f = current["temp_F"]
            feels_f = current["FeelsLikeF"]
            desc = current["weatherDesc"][0]["value"]
            humidity = current["humidity"]
            wind = current["windspeedMiles"]

            # Today's forecast
            today = data["weather"][0]
            high = today["maxtempF"]
            low = today["mintempF"]

            return {
                "temp": temp_f,
                "feels_like": feels_f,
                "description": desc,
                "humidity": humidity,
                "wind_mph": wind,
                "high": high,
                "low": low,
                "city": WEATHER_CITY
            }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Could not fetch weather"}


def get_news_headlines():
    """Get top news headlines."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news("top news today", max_results=5))
        headlines = []
        for r in results:
            headlines.append(r.get("title", ""))
        return headlines
    except:
        return []


def get_date_info():
    """Get formatted date and time info."""
    now = datetime.datetime.now()
    return {
        "date": now.strftime("%A, %B %d, %Y"),
        "time": now.strftime("%I:%M %p"),
        "day_of_week": now.strftime("%A"),
        "greeting": "Good morning" if now.hour < 12
                    else "Good afternoon" if now.hour < 17
                    else "Good evening"
    }


def generate_briefing():
    """
    Gather all briefing data and return a structured summary
    that can be sent to the LLM for a natural Alfred-style delivery.
    """
    date_info = get_date_info()
    weather = get_weather()
    reminders = get_todays_reminders()
    news = get_news_headlines()

    # Build the briefing data
    briefing_parts = []

    # Date and greeting
    briefing_parts.append(
        "Current date: " + date_info["date"] + ", " + date_info["time"]
    )
    briefing_parts.append("Greeting type: " + date_info["greeting"])

    # Weather
    if "error" not in weather:
        briefing_parts.append(
            "Weather in " + weather["city"] + ": " + weather["description"]
            + ", currently " + weather["temp"] + "°F"
            + " (feels like " + weather["feels_like"] + "°F)"
            + ". High " + weather["high"] + "°F, low " + weather["low"] + "°F"
            + ". Humidity " + weather["humidity"] + "%, wind " + weather["wind_mph"] + " mph."
        )
    else:
        briefing_parts.append("Weather: unavailable")

    # Reminders
    if reminders:
        briefing_parts.append(
            "Reminders for today (" + str(len(reminders)) + "): "
            + "; ".join(reminders)
        )
    else:
        briefing_parts.append("No reminders for today.")

    # News
    if news:
        briefing_parts.append(
            "Top headlines: " + " | ".join(news[:4])
        )
    else:
        briefing_parts.append("News: unavailable")

    return "\n".join(briefing_parts)


def get_briefing_prompt():
    """
    Generate the full prompt to send to the LLM for a natural briefing.
    """
    data = generate_briefing()

    prompt = (
        "[DAILY BRIEFING REQUEST]\n"
        "Deliver a morning briefing as Alfred Pennyworth. Use the data below.\n"
        "Be concise but warm. Start with a greeting appropriate to the time of day.\n"
        "Mention the weather naturally, then any reminders, then 2-3 interesting headlines.\n"
        "End with something encouraging or a dry observation.\n"
        "Keep the whole briefing under 8 sentences.\n\n"
        "BRIEFING DATA:\n" + data
    )

    return prompt


# ── Intent Detection ──────────────────────────────────────────
def detect_briefing_command(message):
    """
    Detect if a message is a briefing or reminder command.
    Returns (action, args) or (None, None).
    """
    msg = message.lower().strip()

    # Briefing
    if any(w in msg for w in ["morning briefing", "daily briefing", "brief me",
                               "morning report", "daily report", "whats the briefing",
                               "what's the briefing", "give me a briefing",
                               "good morning", "start my day"]):
        return ("briefing", None)

    # Weather
    if any(w in msg for w in ["whats the weather", "what's the weather",
                               "weather today", "weather outside", "how's the weather",
                               "hows the weather", "is it cold", "is it hot",
                               "is it raining", "will it rain", "temperature"]):
        return ("weather", None)

    # Add reminder
    if any(msg.startswith(w) for w in ["remind me to ", "reminder to ",
                                        "add reminder ", "remember to ",
                                        "dont forget to ", "don't forget to "]):
        text = msg
        for trigger in ["remind me to ", "reminder to ", "add reminder ",
                        "remember to ", "dont forget to ", "don't forget to "]:
            if text.startswith(trigger):
                text = text[len(trigger):]
                break
        return ("add_reminder", text)

    # Check reminders
    if any(w in msg for w in ["my reminders", "what reminders", "any reminders",
                               "check reminders", "show reminders", "pending reminders",
                               "what do i need to do", "what's on my list"]):
        return ("check_reminders", None)

    # Complete reminder
    if any(msg.startswith(w) for w in ["done with ", "completed ", "finished ",
                                        "mark done "]):
        text = msg
        for trigger in ["done with ", "completed ", "finished ", "mark done "]:
            if text.startswith(trigger):
                text = text[len(trigger):]
                break
        return ("complete_reminder", text)

    return (None, None)


def execute_briefing_command(action, args):
    """Execute a briefing/reminder command."""
    if action == "briefing":
        return get_briefing_prompt()
    elif action == "weather":
        w = get_weather()
        if "error" in w:
            return "I'm afraid the weather service is unavailable at the moment, Sir."
        return (
            "Weather in " + w["city"] + ": " + w["description"]
            + ", " + w["temp"] + "°F (feels like " + w["feels_like"] + "°F)."
            + " High of " + w["high"] + "°F, low of " + w["low"] + "°F."
        )
    elif action == "add_reminder":
        return add_reminder(args)
    elif action == "check_reminders":
        reminders = get_todays_reminders()
        if reminders:
            return "Your reminders: " + "; ".join(reminders)
        return "No pending reminders, Sir."
    elif action == "complete_reminder":
        return complete_reminder(args)
    return "Unknown command"
