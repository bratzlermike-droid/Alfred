"""
Chief PC Control — execute local commands on Windows.
Runs entirely on your PC, nothing sent to the server.
"""
import subprocess
import os
import ctypes
import re

# ── App Launcher ───────────────────────────────────────────────
APP_SHORTCUTS = {
    "chrome": "start chrome",
    "google chrome": "start chrome",
    "browser": "start chrome",
    "firefox": "start firefox",
    "edge": "start msedge",
    "notepad": "start notepad",
    "calculator": "start calc",
    "file explorer": "start explorer",
    "explorer": "start explorer",
    "files": "start explorer",
    "task manager": "start taskmgr",
    "command prompt": "start cmd",
    "terminal": "start wt",
    "powershell": "start powershell",
    "spotify": "start spotify",
    "discord": "start discord",
    "steam": "start steam",
    "word": "start winword",
    "excel": "start excel",
    "powerpoint": "start powerpnt",
    "outlook": "start outlook",
    "settings": "start ms-settings:",
    "paint": "start mspaint",
    "snipping tool": "start snippingtool",
    "camera": "start microsoft.windows.camera:",
    "maps": "start bingmaps:",
    "clock": "start ms-clock:",
    "weather": "start bingweather:",
}

def open_app(app_name):
    """Open an application by name."""
    app = app_name.lower().strip()
    if app in APP_SHORTCUTS:
        cmd = APP_SHORTCUTS[app]
        subprocess.Popen(cmd, shell=True)
        return "Opening " + app_name
    else:
        # Try to open it directly
        try:
            subprocess.Popen("start " + app, shell=True)
            return "Trying to open " + app_name
        except:
            return "Could not find application: " + app_name

def close_app(app_name):
    """Close an application by name."""
    app = app_name.lower().strip()
    # Map friendly names to process names
    process_map = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "notepad": "notepad.exe",
        "calculator": "Calculator.exe",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "steam": "steam.exe",
    }
    proc = process_map.get(app, app + ".exe")
    try:
        subprocess.run(["taskkill", "/IM", proc, "/F"],
                       capture_output=True, timeout=5)
        return "Closed " + app_name
    except:
        return "Could not close " + app_name

# ── System Controls ────────────────────────────────────────────
def set_volume(level):
    """Set system volume (0-100)."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100, None)
        return "Volume set to " + str(level) + "%"
    except ImportError:
        # Fallback using nircmd if pycaw not installed
        try:
            vol = int(65535 * level / 100)
            subprocess.run(["nircmd", "setsysvolume", str(vol)], capture_output=True)
            return "Volume set to " + str(level) + "%"
        except:
            return "Could not set volume. Install pycaw: pip install pycaw comtypes"

def mute_volume():
    """Mute system audio."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(1, None)
        return "Audio muted"
    except:
        return "Could not mute audio"

def unmute_volume():
    """Unmute system audio."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(0, None)
        return "Audio unmuted"
    except:
        return "Could not unmute audio"

def lock_screen():
    """Lock the computer."""
    ctypes.windll.user32.LockWorkStation()
    return "Screen locked"

def screenshot():
    """Take a screenshot and save to Desktop."""
    try:
        from PIL import ImageGrab
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.expanduser("~/Desktop/screenshot_" + timestamp + ".png")
        img = ImageGrab.grab()
        img.save(path)
        return "Screenshot saved to Desktop"
    except:
        return "Could not take screenshot"

def get_running_apps():
    """List running applications."""
    try:
        output = subprocess.check_output(
            'tasklist /FI "STATUS eq Running" /FO CSV /NH',
            shell=True
        ).decode()
        apps = set()
        for line in output.strip().split('\n'):
            parts = line.split(',')
            if parts:
                name = parts[0].strip('"').replace('.exe', '')
                if name and not name.startswith('svc') and len(name) > 2:
                    apps.add(name)
        top_apps = sorted(list(apps))[:20]
        return "Running apps: " + ", ".join(top_apps)
    except:
        return "Could not list running apps"

def open_website(url):
    """Open a website in the default browser."""
    if not url.startswith("http"):
        url = "https://" + url
    subprocess.Popen(["start", url], shell=True)
    return "Opening " + url

def run_command(cmd):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=10
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output if output else "Command executed"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return "Command error: " + str(e)

def shutdown_pc(action="shutdown"):
    """Shutdown, restart, or sleep the PC."""
    if action == "shutdown":
        subprocess.Popen("shutdown /s /t 5", shell=True)
        return "Shutting down in 5 seconds"
    elif action == "restart":
        subprocess.Popen("shutdown /r /t 5", shell=True)
        return "Restarting in 5 seconds"
    elif action == "sleep":
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return "Going to sleep"
    elif action == "cancel":
        subprocess.Popen("shutdown /a", shell=True)
        return "Shutdown cancelled"

# ── File Management ────────────────────────────────────────────
def open_folder(path):
    """Open a folder in File Explorer."""
    full_path = os.path.normpath(os.path.expanduser(path))
    if os.path.exists(full_path):
        subprocess.Popen(["explorer", full_path])
        return "Opened " + full_path
    return "Folder not found: " + path

def open_file(path):
    """Open a file with its default application."""
    full_path = os.path.expanduser(path)
    if os.path.exists(full_path):
        os.startfile(full_path)
        return "Opened " + full_path
    return "File not found: " + path

# ── Intent Detection ──────────────────────────────────────────
def detect_pc_command(message):
    """
    Detect if a message is a PC control command.
    Returns (action, args) or (None, None).
    Priority: specific commands first, generic open/close last.
    """
    msg = message.lower().strip()

    # ── Lock screen (check early) ──
    if any(w in msg for w in ["lock screen", "lock computer", "lock my pc",
                               "lock the screen", "lock the computer",
                               "lock my computer", "lock it"]):
        return ("lock_screen", None)

    # ── Volume controls (check early) ──
    if any(w in msg for w in ["volume", "mute", "unmute"]):
        if "unmute" in msg or "un-mute" in msg or "un mute" in msg:
            return ("unmute", None)
        if "mute" in msg:
            return ("mute", None)
        numbers = re.findall(r'\d+', msg)
        if numbers:
            return ("set_volume", int(numbers[0]))
        if any(w in msg for w in ["up", "raise", "increase", "higher", "louder"]):
            return ("set_volume", 80)
        if any(w in msg for w in ["down", "lower", "decrease", "quieter", "softer"]):
            return ("set_volume", 30)
        if "max" in msg:
            return ("set_volume", 100)

    # ── Screenshot ──
    if any(w in msg for w in ["screenshot", "screen shot", "capture screen",
                               "screen capture", "print screen"]):
        return ("screenshot", None)

    # ── Running apps ──
    if any(w in msg for w in ["running apps", "what apps", "what\'s running",
                               "what is running", "list apps", "active apps",
                               "running programs", "open programs"]):
        return ("list_apps", None)

    # ── Shutdown / restart / sleep ──
    if "cancel shutdown" in msg or "cancel restart" in msg:
        return ("shutdown", "cancel")
    if any(w in msg for w in ["shut down", "shutdown", "turn off the computer",
                               "turn off my pc", "turn off my computer", "power off"]):
        return ("shutdown", "shutdown")
    if any(w in msg for w in ["restart", "reboot", "restart the computer",
                               "restart my computer", "restart my pc"]):
        return ("shutdown", "restart")
    if any(w in msg for w in ["go to sleep", "put to sleep", "sleep mode",
                               "hibernate"]):
        return ("shutdown", "sleep")

    # ── Open folders (BEFORE open app) ──
    folders = {
        "documents": "~/Documents",
        "downloads": "~/Downloads",
        "desktop": "~/Desktop",
        "pictures": "~/Pictures",
        "music": "~/Music",
        "videos": "~/Videos",
    }
    for name, path in folders.items():
        if name in msg and any(w in msg for w in ["open", "show", "go to"]):
            return ("open_folder", path)

    # ── Close app ──
    if any(msg.startswith(w) for w in ["close ", "kill ", "quit ", "exit "]):
        app = msg
        for trigger in ["close ", "kill ", "quit ", "exit "]:
            if app.startswith(trigger):
                app = app[len(trigger):]
                break
        return ("close_app", app)

    # ── Open app / website (generic, checked last) ──
    if any(msg.startswith(w) for w in ["open ", "launch ", "start ", "run "]):
        app = msg
        for trigger in ["open ", "launch ", "start ", "run "]:
            if app.startswith(trigger):
                app = app[len(trigger):]
                break
        # Clean up common filler words
        for filler in ["the ", "my ", "up ", "a "]:
            if app.startswith(filler):
                app = app[len(filler):]
        # Check if it's a website
        if "." in app and " " not in app:
            return ("open_website", app)
        # Check if it's a known folder being opened differently
        if app in folders:
            return ("open_folder", folders[app])
        return ("open_app", app)

    return (None, None)


def execute_pc_command(action, args):
    """Execute a PC control command and return the result."""
    if action == "open_app":
        return open_app(args)
    elif action == "close_app":
        return close_app(args)
    elif action == "open_website":
        return open_website(args)
    elif action == "set_volume":
        return set_volume(args)
    elif action == "mute":
        return mute_volume()
    elif action == "unmute":
        return unmute_volume()
    elif action == "lock_screen":
        return lock_screen()
    elif action == "screenshot":
        return screenshot()
    elif action == "list_apps":
        return get_running_apps()
    elif action == "shutdown":
        return shutdown_pc(args)
    elif action == "open_folder":
        return open_folder(args)
    elif action == "run_command":
        return run_command(args)
    return "Unknown command"
