"""
Alfred's Scheduled Routines System
Customizable daily routines with actions.
"""
import json
import os
import datetime
import threading
import time

ROUTINES_FILE = os.path.expanduser("~/alfred_routines.json")

# Default routines
DEFAULT_ROUTINES = {
    "morning": {
        "name": "Morning routine",
        "time": "07:00",
        "enabled": True,
        "greeting": "Good morning, Sir. Allow me to prepare your daily briefing.",
        "actions": [
            {"type": "briefing"},
            {"type": "reminders"},
        ]
    },
    "work_start": {
        "name": "Work start",
        "time": "08:30",
        "enabled": True,
        "greeting": "Time to begin the day's work, Sir. I've prepared your workspace.",
        "actions": [
            {"type": "open_app", "app": "chrome"},
            {"type": "reminders"},
            {"type": "say", "text": "Your workspace is ready. Shall I look into anything specific?"},
        ]
    },
    "lunch": {
        "name": "Lunch break",
        "time": "12:00",
        "enabled": True,
        "greeting": None,
        "actions": [
            {"type": "say", "text": "If I may, Sir, it's noon. Even the most dedicated require sustenance. Might I suggest a brief respite?"},
        ]
    },
    "end_of_work": {
        "name": "End of work",
        "time": "17:00",
        "enabled": True,
        "greeting": None,
        "actions": [
            {"type": "reminders"},
            {"type": "say", "text": "The working day draws to a close, Sir. You have {reminder_count} items remaining. Shall I note anything for tomorrow?"},
        ]
    },
    "wind_down": {
        "name": "Wind down",
        "time": "22:00",
        "enabled": True,
        "greeting": None,
        "actions": [
            {"type": "say", "text": "The hour grows late, Sir. Might I suggest retiring for the evening? I'll keep watch until morning."},
        ]
    }
}


def load_routines():
    """Load routines from file, or create defaults."""
    if os.path.exists(ROUTINES_FILE):
        with open(ROUTINES_FILE, 'r') as f:
            return json.load(f)
    else:
        save_routines(DEFAULT_ROUTINES)
        return DEFAULT_ROUTINES.copy()


def save_routines(routines):
    """Save routines to file."""
    with open(ROUTINES_FILE, 'w') as f:
        json.dump(routines, f, indent=2)


def get_routine(name):
    """Get a specific routine by name."""
    routines = load_routines()
    return routines.get(name)


def set_routine_time(name, new_time):
    """Change the time of a routine. Time format: HH:MM"""
    routines = load_routines()
    if name in routines:
        routines[name]["time"] = new_time
        save_routines(routines)
        return "Updated " + routines[name]["name"] + " to " + new_time
    return "Routine not found: " + name


def toggle_routine(name, enabled=None):
    """Enable or disable a routine."""
    routines = load_routines()
    if name in routines:
        if enabled is None:
            routines[name]["enabled"] = not routines[name]["enabled"]
        else:
            routines[name]["enabled"] = enabled
        state = "enabled" if routines[name]["enabled"] else "disabled"
        save_routines(routines)
        return routines[name]["name"] + " " + state
    return "Routine not found: " + name


def add_custom_routine(name, time_str, message):
    """Add a custom routine."""
    routines = load_routines()
    key = name.lower().replace(" ", "_")
    routines[key] = {
        "name": name,
        "time": time_str,
        "enabled": True,
        "greeting": None,
        "actions": [
            {"type": "say", "text": message}
        ]
    }
    save_routines(routines)
    return "Custom routine '" + name + "' added at " + time_str


def remove_routine(name):
    """Remove a routine."""
    routines = load_routines()
    key = name.lower().replace(" ", "_")
    if key in routines:
        removed = routines.pop(key)
        save_routines(routines)
        return "Removed routine: " + removed["name"]
    return "Routine not found: " + name


def list_routines():
    """List all routines and their status."""
    routines = load_routines()
    lines = []
    for key, r in sorted(routines.items(), key=lambda x: x[1]["time"]):
        status = "ON" if r["enabled"] else "OFF"
        lines.append(r["time"] + " — " + r["name"] + " [" + status + "]")
    return "\n".join(lines) if lines else "No routines configured"


def get_due_routines():
    """Check which routines should fire right now (within 1 minute window)."""
    routines = load_routines()
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M")
    due = []
    for key, r in routines.items():
        if r["enabled"] and r["time"] == current_time:
            due.append((key, r))
    return due


def execute_routine_actions(routine, callbacks):
    """
    Execute the actions in a routine.
    callbacks is a dict with functions:
      - speak(text): speak text
      - briefing(): run briefing
      - open_app(name): open an app
      - get_reminders(): get reminder count
      - add_message(text, sender): add chat message
    """
    from briefing import get_todays_reminders

    results = []

    if routine.get("greeting"):
        callbacks["add_message"](routine["greeting"], "chief")
        callbacks["speak"](routine["greeting"])
        results.append(routine["greeting"])

    for action in routine.get("actions", []):
        action_type = action["type"]

        if action_type == "briefing":
            callbacks["run_briefing"]()

        elif action_type == "reminders":
            reminders = get_todays_reminders()
            if reminders:
                text = "You have " + str(len(reminders)) + " reminders: " + "; ".join(reminders)
            else:
                text = "No pending reminders, Sir."
            callbacks["add_message"](text, "chief")
            callbacks["speak"](text)

        elif action_type == "open_app":
            from pc_control import open_app
            result = open_app(action.get("app", ""))
            results.append(result)

        elif action_type == "say":
            text = action["text"]
            # Replace placeholders
            reminders = get_todays_reminders()
            text = text.replace("{reminder_count}", str(len(reminders)))
            callbacks["add_message"](text, "chief")
            callbacks["speak"](text)
            results.append(text)

        time.sleep(1)  # small pause between actions

    return results


# ── Intent Detection ──────────────────────────────────────────
def detect_routine_command(message):
    """Detect routine-related commands."""
    msg = message.lower().strip()

    # List routines
    if any(w in msg for w in ["list routines", "show routines", "my routines",
                               "what routines", "show my schedule",
                               "whats my schedule", "what's my schedule"]):
        return ("list", None)

    # Run a specific routine manually
    if any(w in msg for w in ["run morning routine", "start morning routine",
                               "morning routine"]):
        return ("run", "morning")
    if any(w in msg for w in ["run work routine", "start work", "work routine"]):
        return ("run", "work_start")
    if any(w in msg for w in ["run wind down", "wind down routine", "bedtime routine",
                               "run bedtime"]):
        return ("run", "wind_down")
    if any(w in msg for w in ["run end of work", "end of work routine",
                               "end work routine"]):
        return ("run", "end_of_work")

    # Enable/disable routines
    if "disable" in msg or "turn off" in msg:
        for name in ["morning", "work_start", "lunch", "end_of_work", "wind_down"]:
            friendly = name.replace("_", " ")
            if friendly in msg or name in msg:
                return ("disable", name)

    if "enable" in msg or "turn on" in msg:
        for name in ["morning", "work_start", "lunch", "end_of_work", "wind_down"]:
            friendly = name.replace("_", " ")
            if friendly in msg or name in msg:
                return ("enable", name)

    # Change routine time
    if "change" in msg and "time" in msg or "move" in msg and "to" in msg:
        import re
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', msg)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            time_str = "{:02d}:{:02d}".format(hour, minute)

            for name in ["morning", "work_start", "lunch", "end_of_work", "wind_down"]:
                friendly = name.replace("_", " ")
                if friendly in msg or name in msg:
                    return ("change_time", (name, time_str))

    return (None, None)


def execute_routine_command(action, args):
    """Execute a routine command (non-run commands only)."""
    if action == "list":
        return list_routines()
    elif action == "disable":
        return toggle_routine(args, False)
    elif action == "enable":
        return toggle_routine(args, True)
    elif action == "change_time":
        name, time_str = args
        return set_routine_time(name, time_str)
    return "Unknown routine command"
