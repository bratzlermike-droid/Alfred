"""
Alfred's Ambient Awareness
Adjusts personality, tone, and proactive behavior based on time, weather, and activity.
"""
import datetime
import time
import os
import json
import requests
import threading

SESSION_FILE = os.path.expanduser("~/alfred_session.json")
WEATHER_CITY = "Reno+Nevada"


def get_time_context():
    """Get rich time-based context."""
    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.strftime("%A")
    is_weekend = now.weekday() >= 5
    month = now.month

    # Time of day
    if 5 <= hour < 8:
        period = "early_morning"
        energy = "gentle"
        greeting = "Good morning, Sir. An early start today."
    elif 8 <= hour < 12:
        period = "morning"
        energy = "focused"
        greeting = "Good morning, Sir."
    elif 12 <= hour < 13:
        period = "midday"
        energy = "moderate"
        greeting = "Good afternoon, Sir. I trust you've eaten."
    elif 13 <= hour < 17:
        period = "afternoon"
        energy = "steady"
        greeting = "Good afternoon, Sir."
    elif 17 <= hour < 20:
        period = "evening"
        energy = "winding"
        greeting = "Good evening, Sir."
    elif 20 <= hour < 23:
        period = "night"
        energy = "calm"
        greeting = "Getting rather late, Sir."
    else:
        period = "late_night"
        energy = "concerned"
        greeting = "Sir, I feel compelled to note the hour. Even Gotham sleeps eventually."

    # Season
    if month in [12, 1, 2]:
        season = "winter"
    elif month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    else:
        season = "autumn"

    return {
        "hour": hour,
        "period": period,
        "energy": energy,
        "greeting": greeting,
        "weekday": weekday,
        "is_weekend": is_weekend,
        "season": season,
        "date": now.strftime("%B %d, %Y"),
        "time": now.strftime("%I:%M %p")
    }


def get_weather_context():
    """Get current weather for ambient awareness."""
    try:
        r = requests.get(
            "https://wttr.in/" + WEATHER_CITY + "?format=j1",
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            current = data["current_condition"][0]
            return {
                "temp_f": int(current["temp_F"]),
                "description": current["weatherDesc"][0]["value"].lower(),
                "humidity": int(current["humidity"]),
                "is_rainy": any(w in current["weatherDesc"][0]["value"].lower()
                               for w in ["rain", "drizzle", "shower", "storm"]),
                "is_cold": int(current["temp_F"]) < 40,
                "is_hot": int(current["temp_F"]) > 90,
                "is_nice": 60 <= int(current["temp_F"]) <= 80 and
                           "clear" in current["weatherDesc"][0]["value"].lower()
            }
    except:
        pass
    return None


def load_session():
    """Load session tracking data."""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r') as f:
            return json.load(f)
    return {
        "session_start": None,
        "last_interaction": None,
        "interaction_count": 0,
        "break_reminder_sent": False
    }


def save_session(session):
    """Save session data."""
    with open(SESSION_FILE, 'w') as f:
        json.dump(session, f, indent=2)


def track_interaction():
    """Track that an interaction occurred."""
    session = load_session()
    now = datetime.datetime.now().isoformat()

    if session["session_start"] is None:
        session["session_start"] = now

    session["last_interaction"] = now
    session["interaction_count"] += 1
    save_session(session)
    return session


def get_session_duration():
    """Get how long the current session has been."""
    session = load_session()
    if not session["session_start"]:
        return 0
    start = datetime.datetime.fromisoformat(session["session_start"])
    return (datetime.datetime.now() - start).total_seconds() / 3600  # hours


def reset_session():
    """Reset session tracking."""
    save_session({
        "session_start": None,
        "last_interaction": None,
        "interaction_count": 0,
        "break_reminder_sent": False
    })


def get_proactive_suggestion():
    """Generate a proactive suggestion based on current context."""
    ctx = get_time_context()
    weather = get_weather_context()
    hours_active = get_session_duration()
    session = load_session()

    suggestions = []

    # Break reminder after 2+ hours
    if hours_active >= 2 and not session.get("break_reminder_sent"):
        suggestions.append(
            "You've been at it for " + str(round(hours_active, 1))
            + " hours, Sir. Might I suggest a brief stretch?"
        )
        session["break_reminder_sent"] = True
        save_session(session)

    # Reset break reminder after 4 hours
    if hours_active >= 4 and session.get("break_reminder_sent"):
        session["break_reminder_sent"] = False
        save_session(session)

    # Weather suggestions
    if weather:
        if weather["is_nice"] and ctx["period"] in ["morning", "afternoon"]:
            suggestions.append(
                "Rather pleasant outside, Sir — " + str(weather["temp_f"])
                + " degrees and " + weather["description"]
                + ". Perhaps worth a brief constitutional."
            )
        elif weather["is_rainy"]:
            suggestions.append(
                "It appears to be " + weather["description"]
                + " outside. An umbrella would be prudent should you venture out."
            )
        elif weather["is_cold"]:
            suggestions.append(
                "It's " + str(weather["temp_f"])
                + " degrees outside, Sir. Do dress warmly."
            )

    # Late night concern
    if ctx["period"] == "late_night":
        suggestions.append(
            "I don't wish to overstep, Sir, but it is " + ctx["time"]
            + ". Adequate rest is essential, even for those with ambitious projects."
        )

    # Weekend morning
    if ctx["is_weekend"] and ctx["period"] == "morning":
        suggestions.append(
            "It's " + ctx["weekday"] + " morning, Sir. No scheduled obligations. "
            "A fine opportunity to pursue personal interests."
        )

    return suggestions[0] if suggestions else None


def get_ambient_prompt_modifier():
    """
    Generate a modifier for the system prompt based on current context.
    This adjusts Alfred's tone and awareness.
    """
    ctx = get_time_context()
    weather = get_weather_context()
    hours_active = get_session_duration()

    modifier = "\n\n[AMBIENT CONTEXT — adjust your tone accordingly]:\n"
    modifier += "Time: " + ctx["time"] + " (" + ctx["period"] + ", " + ctx["weekday"] + ")\n"
    modifier += "Energy level: " + ctx["energy"] + "\n"
    modifier += "Season: " + ctx["season"] + "\n"

    if weather:
        modifier += "Weather: " + str(weather["temp_f"]) + "°F, " + weather["description"] + "\n"

    if hours_active > 0:
        modifier += "User has been active for " + str(round(hours_active, 1)) + " hours\n"

    # Tone guidance
    if ctx["energy"] == "gentle":
        modifier += "Tone: Speak softly. The day is young.\n"
    elif ctx["energy"] == "focused":
        modifier += "Tone: Crisp and efficient. Support productivity.\n"
    elif ctx["energy"] == "winding":
        modifier += "Tone: Warmer, more conversational. The work day is ending.\n"
    elif ctx["energy"] == "calm":
        modifier += "Tone: Quiet, reflective. Wind down the evening.\n"
    elif ctx["energy"] == "concerned":
        modifier += "Tone: Gently suggest rest. Express quiet concern for wellbeing.\n"

    return modifier


def get_orb_color_for_time():
    """Return RGB color tuple for the orb based on time of day."""
    ctx = get_time_context()

    colors = {
        "early_morning": (180, 140, 60),    # warm gold — sunrise
        "morning": (0, 140, 220),            # clear blue — focused
        "midday": (0, 180, 160),             # teal — balanced
        "afternoon": (0, 140, 220),          # blue — steady
        "evening": (160, 100, 200),          # soft purple — winding down
        "night": (80, 60, 160),              # deep purple — calm
        "late_night": (60, 40, 100),         # dim violet — rest
    }

    return colors.get(ctx["period"], (0, 140, 220))
