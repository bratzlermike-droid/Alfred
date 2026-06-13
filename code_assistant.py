"""
Alfred's Clipboard Manager
Tracks copy history and allows searching past clips.
"""
import threading
import time
import datetime
import re

_clipboard_history = []
_max_history = 50
_monitoring = False
_last_content = ""


def start_monitoring():
    """Start monitoring clipboard in background."""
    global _monitoring
    if _monitoring:
        return
    _monitoring = True
    threading.Thread(target=_monitor_loop, daemon=True).start()


def stop_monitoring():
    global _monitoring
    _monitoring = False


def _monitor_loop():
    """Background loop that watches for clipboard changes."""
    global _last_content
    import win32clipboard

    while _monitoring:
        try:
            win32clipboard.OpenClipboard()
            try:
                content = win32clipboard.GetClipboardData()
            except:
                content = None
            win32clipboard.CloseClipboard()

            if content and content != _last_content and isinstance(content, str):
                _last_content = content
                _clipboard_history.append({
                    "content": content[:500],  # limit size
                    "timestamp": datetime.datetime.now().isoformat(),
                    "preview": content[:80].replace("\n", " ")
                })
                # Trim history
                if len(_clipboard_history) > _max_history:
                    _clipboard_history.pop(0)
        except:
            pass
        time.sleep(1)


def get_clipboard_history(count=10):
    """Get recent clipboard history."""
    if not _clipboard_history:
        return "No clipboard history yet, Sir. I'll begin tracking from now."

    items = _clipboard_history[-count:]
    items.reverse()

    lines = "Recent clipboard (" + str(len(items)) + " items):\n"
    for i, item in enumerate(items, 1):
        time_str = item["timestamp"][11:16]
        preview = item["preview"][:50]
        lines += "  " + str(i) + ". [" + time_str + "] " + preview + "\n"
    return lines.strip()


def get_last_clip():
    """Get the most recent clipboard item."""
    if not _clipboard_history:
        return "No clipboard history available."
    item = _clipboard_history[-1]
    return "Last copied: " + item["content"][:200]


def search_clipboard(query):
    """Search clipboard history."""
    query_lower = query.lower()
    results = []
    for item in reversed(_clipboard_history):
        if query_lower in item["content"].lower():
            results.append(item)
        if len(results) >= 5:
            break

    if not results:
        return "Nothing matching '" + query + "' in clipboard history."

    lines = "Clipboard matches for '" + query + "':\n"
    for item in results:
        time_str = item["timestamp"][11:16]
        preview = item["preview"][:60]
        lines += "  [" + time_str + "] " + preview + "\n"
    return lines.strip()


def get_clip_by_index(index):
    """Get a specific clipboard item by index (1 = most recent)."""
    if not _clipboard_history or index < 1 or index > len(_clipboard_history):
        return "Clip not found."
    item = _clipboard_history[-index]
    return item["content"][:500]


# ── Intent Detection ──────────────────────────────────────────
def detect_clipboard_command(message):
    msg = message.lower().strip()

    if any(w in msg for w in ["clipboard history", "copy history", "what have i copied",
                               "what did i copy", "show clipboard", "my clipboard"]):
        return ("history", None)

    if any(w in msg for w in ["last thing i copied", "last copy", "last clip",
                               "what was that i copied", "paste history"]):
        return ("last", None)

    search_match = re.search(r'(?:search|find) (?:clipboard|copies|clips?) (?:for )?(.+)', msg)
    if search_match:
        return ("search", search_match.group(1).strip())

    if any(w in msg for w in ["copied earlier", "copy earlier", "that thing i copied"]):
        return ("history", None)

    return (None, None)


def execute_clipboard_command(action, args):
    if action == "history":
        return get_clipboard_history()
    elif action == "last":
        return get_last_clip()
    elif action == "search":
        return search_clipboard(args)
    return "Unknown clipboard command"
