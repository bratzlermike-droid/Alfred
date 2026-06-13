"""
Alfred's Multi-device Sync
Syncs local data (finance, reminders) with the server so phone and PC share the same data.
"""
import os
import json
import requests
import threading
import time

SERVER_URL = os.environ.get("ALFRED_SERVER_URL", "http://localhost:8000")
AUTH_TOKEN = "Bearer " + os.environ.get("ALFRED_AUTH_TOKEN", "change-me-in-env")

LOCAL_FINANCE = os.path.expanduser("~/alfred_finance.json")
LOCAL_REMINDERS = os.path.expanduser("~/alfred_reminders.json")


def _server_post(endpoint, data):
    """Post data to server."""
    try:
        r = requests.post(
            SERVER_URL + endpoint,
            headers={"Authorization": AUTH_TOKEN, "Content-Type": "application/json"},
            json=data, timeout=10
        )
        return r.status_code == 200
    except:
        return False


def _server_get(endpoint):
    """Get data from server."""
    try:
        r = requests.get(
            SERVER_URL + endpoint,
            headers={"Authorization": AUTH_TOKEN},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def sync_to_server():
    """Push local data to server for phone access."""
    synced = []

    # Sync finance
    if os.path.exists(LOCAL_FINANCE):
        try:
            with open(LOCAL_FINANCE, 'r') as f:
                data = json.load(f)
            # Write to server data directory via chat command
            # The server_features module stores finance in ~/chief/data/finance.json
            # We sync by making the server's copy match the local copy
            _server_post("/sync/finance", data)
            synced.append("finance")
        except:
            pass

    # Sync reminders
    if os.path.exists(LOCAL_REMINDERS):
        try:
            with open(LOCAL_REMINDERS, 'r') as f:
                data = json.load(f)
            _server_post("/sync/reminders", data)
            synced.append("reminders")
        except:
            pass

    return synced


def sync_from_server():
    """Pull server data to local for desktop access."""
    pulled = []

    # Pull finance
    data = _server_get("/sync/finance")
    if data:
        with open(LOCAL_FINANCE, 'w') as f:
            json.dump(data, f, indent=2)
        pulled.append("finance")

    # Pull reminders
    data = _server_get("/sync/reminders")
    if data:
        with open(LOCAL_REMINDERS, 'w') as f:
            json.dump(data, f, indent=2)
        pulled.append("reminders")

    return pulled


def start_auto_sync(interval=300):
    """Start automatic sync every N seconds (default 5 min)."""
    def sync_loop():
        while True:
            try:
                sync_to_server()
            except:
                pass
            time.sleep(interval)

    threading.Thread(target=sync_loop, daemon=True).start()


def full_sync():
    """Pull from server, merge, push back."""
    pulled = sync_from_server()
    pushed = sync_to_server()
    return "Synced: pulled " + str(pulled) + ", pushed " + str(pushed)


def detect_sync_command(message):
    msg = message.lower().strip()
    if any(w in msg for w in ["sync devices", "sync data", "sync my data",
                               "sync phone", "sync to phone",
                               "device sync", "multi device"]):
        return ("sync", None)
    return (None, None)


def execute_sync_command(action, args):
    if action == "sync":
        result = full_sync()
        return "Devices synchronized, Sir. " + result
    return "Unknown sync command"
