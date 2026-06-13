"""
Alfred's Custom Command System
User-defined voice macros that trigger action sequences.
"Protocol Alpha" = your custom workflow.
"""
import json
import os
import time
import subprocess
import threading

COMMANDS_FILE = os.path.expanduser("~/alfred_commands.json")

# Default protocols
DEFAULT_COMMANDS = {
    "protocol alpha": {
        "name": "Protocol Alpha",
        "description": "Full morning startup sequence",
        "actions": [
            {"type": "say", "text": "Initiating Protocol Alpha, Sir."},
            {"type": "briefing"},
            {"type": "email_check"},
            {"type": "calendar_check"},
            {"type": "open_app", "app": "chrome"},
            {"type": "say", "text": "All systems ready. Protocol Alpha complete."},
        ]
    },
    "protocol omega": {
        "name": "Protocol Omega",
        "description": "End of day shutdown sequence",
        "actions": [
            {"type": "say", "text": "Initiating shutdown protocol, Sir."},
            {"type": "sync"},
            {"type": "say", "text": "Data synchronized. Shall I close your applications?"},
        ]
    },
    "protocol sentinel": {
        "name": "Protocol Sentinel",
        "description": "Full security and system diagnostic",
        "actions": [
            {"type": "say", "text": "Running full diagnostic, Sir."},
            {"type": "system_status"},
            {"type": "security_scan"},
            {"type": "say", "text": "Diagnostic complete."},
        ]
    },
    "battle stations": {
        "name": "Battle Stations",
        "description": "Focus mode — close distractions, open work tools",
        "actions": [
            {"type": "say", "text": "Battle stations, Sir. Clearing distractions."},
            {"type": "close_app", "app": "discord"},
            {"type": "close_app", "app": "spotify"},
            {"type": "say", "text": "Workspace cleared. Full focus mode engaged."},
        ]
    },
    "stand down": {
        "name": "Stand Down",
        "description": "Relax mode — open entertainment",
        "actions": [
            {"type": "say", "text": "Standing down, Sir. You've earned a rest."},
            {"type": "open_app", "app": "spotify"},
            {"type": "say", "text": "Spotify is ready. Shall I play something?"},
        ]
    },
}


def load_commands():
    if os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, 'r') as f:
            return json.load(f)
    save_commands(DEFAULT_COMMANDS)
    return DEFAULT_COMMANDS.copy()


def save_commands(commands):
    with open(COMMANDS_FILE, 'w') as f:
        json.dump(commands, f, indent=2)


def list_commands():
    """List all custom commands."""
    commands = load_commands()
    if not commands:
        return "No custom commands configured, Sir."
    lines = "Available protocols:\n"
    for trigger, cmd in sorted(commands.items()):
        lines += '  "' + trigger.title() + '" — ' + cmd["description"] + "\n"
    return lines.strip()


def add_command(trigger, description, action_texts):
    """Add a new custom command."""
    commands = load_commands()
    actions = []
    for text in action_texts:
        actions.append({"type": "say", "text": text})
    commands[trigger.lower()] = {
        "name": trigger.title(),
        "description": description,
        "actions": actions
    }
    save_commands(commands)
    return 'Protocol "' + trigger.title() + '" created.'


def remove_command(trigger):
    """Remove a custom command."""
    commands = load_commands()
    key = trigger.lower()
    if key in commands:
        name = commands[key]["name"]
        del commands[key]
        save_commands(commands)
        return 'Protocol "' + name + '" removed.'
    return "Protocol not found."


def execute_command(trigger, callbacks):
    """
    Execute a custom command sequence.
    callbacks: dict with speak, add_message, run_briefing, check_email,
               check_calendar, system_status, security_scan, open_app,
               close_app, sync
    """
    commands = load_commands()
    key = trigger.lower()
    if key not in commands:
        return None

    cmd = commands[key]
    results = []

    for action in cmd["actions"]:
        atype = action["type"]

        if atype == "say":
            text = action["text"]
            callbacks["add_message"](text, "chief")
            callbacks["speak"](text)

        elif atype == "briefing":
            callbacks["run_command"]("brief me")

        elif atype == "email_check":
            callbacks["run_command"]("check my email")

        elif atype == "calendar_check":
            callbacks["run_command"]("whats on my calendar")

        elif atype == "system_status":
            callbacks["run_command"]("system status")

        elif atype == "security_scan":
            callbacks["run_command"]("run security scan")

        elif atype == "sync":
            callbacks["run_command"]("sync devices")

        elif atype == "open_app":
            try:
                from pc_control import open_app
                result = open_app(action.get("app", ""))
                callbacks["add_message"](result, "chief")
            except:
                pass

        elif atype == "close_app":
            try:
                from pc_control import close_app
                result = close_app(action.get("app", ""))
                callbacks["add_message"](result, "chief")
            except:
                pass

        time.sleep(1.5)

    return cmd["name"] + " complete."


# ── Intent Detection ──────────────────────────────────────────
def detect_custom_command(message):
    msg = message.lower().strip()

    # List commands
    if any(w in msg for w in ["list protocols", "my protocols", "show protocols",
                               "custom commands", "list commands", "show commands",
                               "what protocols"]):
        return ("list", None)

    # Check if message matches a protocol trigger
    commands = load_commands()
    for trigger in commands:
        if trigger in msg:
            return ("execute", trigger)

    return (None, None)
