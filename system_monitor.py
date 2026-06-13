"""
Server-side features for Alfred's web interface.
Briefing, weather, reminders, and finance — accessible from any device.
"""
import json
import os
import re
import datetime
import requests

DATA_DIR = os.path.expanduser("~/chief/data")
os.makedirs(DATA_DIR, exist_ok=True)

REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
FINANCE_FILE = os.path.join(DATA_DIR, "finance.json")
WEATHER_CITY = "Reno+Nevada"


# ── Helpers ────────────────────────────────────────────────────
def _load_json(path, default):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return default

def _save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


# ── Weather ────────────────────────────────────────────────────
def get_weather():
    try:
        r = requests.get("https://wttr.in/" + WEATHER_CITY + "?format=j1", timeout=5)
        if r.status_code == 200:
            d = r.json()
            c = d["current_condition"][0]
            t = d["weather"][0]
            return (c["weatherDesc"][0]["value"] + ", " + c["temp_F"] + "F"
                    + " (feels " + c["FeelsLikeF"] + "F). High " + t["maxtempF"]
                    + "F, low " + t["mintempF"] + "F.")
    except:
        pass
    return "Weather unavailable."


# ── News ───────────────────────────────────────────────────────
def get_news():
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news("top news today", max_results=4))
        return [r.get("title", "") for r in results]
    except:
        return []


# ── Reminders ──────────────────────────────────────────────────
def add_reminder(text):
    reminders = _load_json(REMINDERS_FILE, [])
    reminders.append({"text": text, "date": datetime.date.today().isoformat(), "done": False})
    _save_json(REMINDERS_FILE, reminders)
    return "Reminder added: " + text

def get_reminders():
    reminders = _load_json(REMINDERS_FILE, [])
    today = datetime.date.today().isoformat()
    active = [r["text"] for r in reminders if not r["done"] and r["date"] <= today]
    return active

def complete_reminder(text):
    reminders = _load_json(REMINDERS_FILE, [])
    for r in reminders:
        if text.lower() in r["text"].lower() and not r["done"]:
            r["done"] = True
            _save_json(REMINDERS_FILE, reminders)
            return "Done: " + r["text"]
    return "Reminder not found."


# ── Finance ────────────────────────────────────────────────────
def add_expense(amount, category):
    data = _load_json(FINANCE_FILE, {"expenses": [], "budgets": {}, "watchlist": []})
    data["expenses"].append({
        "amount": round(float(amount), 2), "category": category,
        "date": datetime.date.today().isoformat()
    })
    _save_json(FINANCE_FILE, data)
    return "Noted: $" + str(round(float(amount), 2)) + " on " + category

def get_spending():
    data = _load_json(FINANCE_FILE, {"expenses": [], "budgets": {}, "watchlist": []})
    month = datetime.date.today().replace(day=1).isoformat()
    expenses = [e for e in data["expenses"] if e["date"] >= month]
    if not expenses:
        return "No expenses this month."
    total = sum(e["amount"] for e in expenses)
    cats = {}
    for e in expenses:
        cats[e["category"]] = cats.get(e["category"], 0) + e["amount"]
    lines = "This month: $" + str(round(total, 2))
    for c, a in sorted(cats.items(), key=lambda x: -x[1]):
        lines += " | " + c + ": $" + str(round(a, 2))
    return lines

def get_stock(symbol):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol.upper()
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code == 200:
            meta = r.json()["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            prev = meta.get("chartPreviousClose", price)
            pct = round((price - prev) / prev * 100, 2) if prev else 0
            arrow = "up" if pct >= 0 else "down"
            return symbol.upper() + ": $" + str(round(price, 2)) + " (" + arrow + " " + str(abs(pct)) + "%)"
    except:
        pass
    return "Could not find " + symbol


# ── Briefing ───────────────────────────────────────────────────
def get_briefing():
    from datetime import timezone, timedelta
    pacific = timezone(timedelta(hours=-7))
    now = datetime.datetime.now(pacific)
    
    parts = []
    parts.append("Date: " + now.strftime("%A, %B %d, %Y, %I:%M %p"))
    parts.append("Weather: " + get_weather())
    
    reminders = get_reminders()
    if reminders:
        parts.append("Reminders (" + str(len(reminders)) + "): " + "; ".join(reminders))
    
    news = get_news()
    if news:
        parts.append("Headlines: " + " | ".join(news[:3]))
    
    return "\n".join(parts)


# ── Intent Detection ──────────────────────────────────────────
def detect_server_feature(message):
    """Detect if a message should be handled by server features.
    Returns (action, args, response) or (None, None, None).
    """
    msg = message.lower().strip()
    
    # Strip the [LONG RESPONSE OK] tag for detection
    clean = msg.replace("[long response ok]", "").strip()

    # Briefing
    if any(w in clean for w in ["morning briefing", "daily briefing", "brief me",
                                 "good morning", "start my day"]):
        data = get_briefing()
        return ("briefing", None, "[BRIEFING DATA]\n" + data + "\nDeliver this as Alfred in 3-4 sentences.")

    # Weather
    if any(w in clean for w in ["weather", "temperature", "is it cold",
                                 "is it hot", "is it raining"]):
        return ("direct", None, get_weather())

    # Add reminder
    for trigger in ["remind me to ", "reminder to ", "remember to "]:
        if clean.startswith(trigger):
            text = clean[len(trigger):]
            return ("direct", None, add_reminder(text))

    # Check reminders
    if any(w in clean for w in ["my reminders", "any reminders", "check reminders"]):
        reminders = get_reminders()
        if reminders:
            return ("direct", None, "Your reminders: " + "; ".join(reminders))
        return ("direct", None, "No pending reminders, Sir.")

    # Complete reminder
    for trigger in ["done with ", "completed ", "finished "]:
        if clean.startswith(trigger):
            return ("direct", None, complete_reminder(clean[len(trigger):]))

    # Add expense
    spent_match = re.search(r'(?:i\s+)?spent\s+\$?(\d+\.?\d*)\s+(?:on|at|for)\s+(\w+)', clean)
    if spent_match:
        return ("direct", None, add_expense(float(spent_match.group(1)), spent_match.group(2)))

    # Spending summary
    if any(w in clean for w in ["spending", "how much have i spent", "monthly spending"]):
        return ("direct", None, get_spending())

    # Stock check
    stock_match = re.search(r'(?:price of|check|how is|how\'s)\s+([a-z]{1,5})(?:\s+stock)?', clean)
    if stock_match and any(w in clean for w in ["stock", "price", "trading"]):
        return ("direct", None, get_stock(stock_match.group(1)))

    return (None, None, None)
