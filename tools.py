"""
Chief's tools — web search, weather, time, timers, system info.
Polished with better intent detection.
"""
import datetime
import subprocess
import threading
import re
from ddgs import DDGS

# ── Web Search ─────────────────────────────────────────────────
def web_search(query, max_results=3):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found for: " + query
        output = "Search results for: " + query + "\n\n"
        for i, r in enumerate(results, 1):
            output += str(i) + ". " + r.get("title", "") + "\n"
            output += "   " + r.get("body", "") + "\n"
            output += "   " + r.get("href", "") + "\n\n"
        return output.strip()
    except Exception as e:
        return "Search error: " + str(e)

# ── Date and Time ──────────────────────────────────────────────
def get_datetime():
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %B %d %Y. The time is %I:%M %p.")

# ── System Info ────────────────────────────────────────────────
def get_system_info():
    try:
        cpu = subprocess.check_output(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'", shell=True
        ).decode().strip()
        mem = subprocess.check_output(
            "free -h | grep Mem | awk '{print $3\"/\"$2}'", shell=True
        ).decode().strip()
        uptime = subprocess.check_output("uptime -p", shell=True).decode().strip()
        disk = subprocess.check_output(
            "df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\" used)\"}'", shell=True
        ).decode().strip()
        return "CPU: " + cpu + "% | RAM: " + mem + " | Disk: " + disk + " | " + uptime
    except Exception as e:
        return "System info error: " + str(e)

# ── Timers ─────────────────────────────────────────────────────
active_timers = {}

def set_timer(seconds, label="Timer"):
    try:
        seconds = int(seconds)
        def timer_done():
            active_timers.pop(label, None)
            print("TIMER DONE: " + label)

        t = threading.Timer(seconds, timer_done)
        t.start()
        active_timers[label] = t

        if seconds >= 3600:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return "Timer set for " + str(hours) + " hour(s) and " + str(mins) + " minute(s)."
        elif seconds >= 60:
            mins = seconds // 60
            secs = seconds % 60
            return "Timer set for " + str(mins) + " minute(s) and " + str(secs) + " second(s)."
        return "Timer set for " + str(seconds) + " second(s)."
    except Exception as e:
        return "Timer error: " + str(e)

# ── News Headlines ─────────────────────────────────────────────
def get_news(topic="world news", max_results=5):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(topic, max_results=max_results))
        if not results:
            return "No news found for: " + topic
        output = "Latest news on " + topic + ":\n\n"
        for i, r in enumerate(results, 1):
            output += str(i) + ". " + r.get("title", "") + "\n"
            output += "   " + r.get("body", "")[:200] + "\n\n"
        return output.strip()
    except Exception as e:
        return "News error: " + str(e)

# ── Calculator ─────────────────────────────────────────────────
def calculate(expression):
    try:
        # Clean up natural language math
        expr = expression.lower()
        expr = expr.replace("times", "*").replace("multiplied by", "*")
        expr = expr.replace("divided by", "/").replace("over", "/")
        expr = expr.replace("plus", "+").replace("added to", "+")
        expr = expr.replace("minus", "-").replace("subtract", "-")
        expr = expr.replace("to the power of", "**").replace("squared", "**2")
        expr = expr.replace("x", "*")

        # Keep only math characters
        clean = re.sub(r'[^0-9+\-*/().\s]', '', expr).strip()
        if not clean or not any(c.isdigit() for c in clean):
            return "Could not parse a math expression from that."

        result = eval(clean)
        return str(expression) + " = " + str(result)
    except Exception as e:
        return "Calculation error: " + str(e)

# ── Intent detection ───────────────────────────────────────────
def detect_tool(message):
    msg = message.lower().strip()

    # Date / time — broad detection
    time_words = [
        "what time", "what's the time", "current time", "tell me the time",
        "what date", "what day", "today's date", "what is the date",
        "what is the time", "what's today", "what day is it"
    ]
    if any(w in msg for w in time_words):
        return ("get_datetime", None)

    # News — check BEFORE web search
    news_words = [
        "news", "headlines", "what's happening in",
        "current events", "latest on", "latest in"
    ]
    if any(w in msg for w in news_words):
        topic = msg
        for trigger in [
            "search for the latest in", "search for the latest",
            "search for", "get me the", "give me the",
            "latest news on", "latest news about", "latest news in",
            "news about", "news on", "news in",
            "headlines about", "headlines on",
            "what's happening in", "what's happening with",
            "tell me the latest", "latest on", "latest in"
        ]:
            topic = topic.replace(trigger, "").strip()
        # Clean leftover words
        for filler in ["the", "some", "any", "me", "get", "find", "show"]:
            if topic.startswith(filler + " "):
                topic = topic[len(filler) + 1:]
        topic = topic.strip() if topic.strip() else "world news"
        return ("get_news", topic)

    # Web search
    search_words = [
        "search", "look up", "find information", "search the web",
        "google", "look for", "find out", "research",
        "what is a ", "what is an ", "what are ", "who is ", "who are ",
        "how does ", "how do ", "how to ", "tell me about", "explain"
    ]
    if any(w in msg for w in search_words):
        query = msg
        for trigger in [
            "search the web for", "search for", "look up",
            "search", "google", "find information about",
            "find information on", "look for", "find out about",
            "find out", "research", "tell me about", "explain"
        ]:
            query = query.replace(trigger, "").strip()
        if query:
            return ("web_search", query)

    # Timer
    timer_words = [
        "set a timer", "timer for", "set timer", "start a timer",
        "remind me in", "countdown", "wake me in", "alert me in"
    ]
    if any(w in msg for w in timer_words):
        numbers = re.findall(r'\d+', msg)
        if numbers:
            seconds = int(numbers[0])
            if "hour" in msg:
                seconds *= 3600
            elif "minute" in msg or "min" in msg:
                seconds *= 60
            return ("set_timer", seconds)

    # Calculator — detect math expressions
    math_words = [
        "calculate", "what is", "how much is", "what's",
        "multiply", "divide", "plus", "minus", "times",
        "added to", "subtracted", "sum of", "product of"
    ]
    if any(w in msg for w in math_words):
        # Check there are actually numbers to calculate
        if re.search(r'\d+\s*[\+\-\*\/x]\s*\d+', msg) or \
           re.search(r'\d+\s+(times|plus|minus|divided|multiplied)', msg):
            return ("calculate", msg)

    # System info
    system_words = [
        "system info", "server status", "cpu usage", "memory usage",
        "how is the server", "server health", "disk space",
        "how much ram", "server stats"
    ]
    if any(w in msg for w in system_words):
        return ("get_system_info", None)

    return (None, None)


TOOLS = {
    "web_search":      web_search,
    "get_datetime":    get_datetime,
    "get_system_info": get_system_info,
    "set_timer":       set_timer,
    "get_news":        get_news,
    "calculate":       calculate,
}
