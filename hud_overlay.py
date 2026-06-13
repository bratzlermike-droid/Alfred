"""
Alfred's Finance Tracker
Track spending, budgets, and stock watchlist by voice.
"""
import json
import os
import re
import datetime
import requests

FINANCE_FILE = os.path.expanduser("~/alfred_finance.json")


def _load_data():
    if os.path.exists(FINANCE_FILE):
        with open(FINANCE_FILE, 'r') as f:
            return json.load(f)
    default = {
        "expenses": [],
        "budgets": {},
        "watchlist": []
    }
    _save_data(default)
    return default


def _save_data(data):
    with open(FINANCE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# ── Expense Tracking ──────────────────────────────────────────
def add_expense(amount, category, description=""):
    """Add an expense."""
    data = _load_data()
    entry = {
        "amount": round(float(amount), 2),
        "category": category.lower().strip(),
        "description": description,
        "date": datetime.date.today().isoformat(),
        "timestamp": datetime.datetime.now().isoformat()
    }
    data["expenses"].append(entry)
    _save_data(data)
    return ("Noted: $" + str(entry["amount"]) + " on " + category
            + (" — " + description if description else ""))


def get_spending_today():
    """Get today's total spending."""
    data = _load_data()
    today = datetime.date.today().isoformat()
    total = sum(e["amount"] for e in data["expenses"] if e["date"] == today)
    items = [e for e in data["expenses"] if e["date"] == today]

    if not items:
        return "No expenses recorded today, Sir."

    lines = "Today's spending: $" + str(round(total, 2)) + "\n"
    for e in items:
        lines += "  $" + str(e["amount"]) + " — " + e["category"]
        if e["description"]:
            lines += " (" + e["description"] + ")"
        lines += "\n"
    return lines.strip()


def get_spending_week():
    """Get this week's spending by category."""
    data = _load_data()
    today = datetime.date.today()
    week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()

    week_expenses = [e for e in data["expenses"] if e["date"] >= week_start]
    if not week_expenses:
        return "No expenses recorded this week, Sir."

    total = sum(e["amount"] for e in week_expenses)
    categories = {}
    for e in week_expenses:
        cat = e["category"]
        categories[cat] = categories.get(cat, 0) + e["amount"]

    lines = "This week's spending: $" + str(round(total, 2)) + "\n"
    for cat, amt in sorted(categories.items(), key=lambda x: -x[1]):
        lines += "  " + cat.title() + ": $" + str(round(amt, 2)) + "\n"
    return lines.strip()


def get_spending_month():
    """Get this month's spending by category."""
    data = _load_data()
    month_start = datetime.date.today().replace(day=1).isoformat()

    month_expenses = [e for e in data["expenses"] if e["date"] >= month_start]
    if not month_expenses:
        return "No expenses recorded this month, Sir."

    total = sum(e["amount"] for e in month_expenses)
    categories = {}
    for e in month_expenses:
        cat = e["category"]
        categories[cat] = categories.get(cat, 0) + e["amount"]

    lines = "This month's spending: $" + str(round(total, 2)) + "\n"
    for cat, amt in sorted(categories.items(), key=lambda x: -x[1]):
        lines += "  " + cat.title() + ": $" + str(round(amt, 2)) + "\n"

    # Check against budgets
    budgets = data.get("budgets", {})
    for cat, budget in budgets.items():
        spent = categories.get(cat, 0)
        if spent > budget:
            lines += "\n  Warning: " + cat.title() + " is $" + str(round(spent - budget, 2)) + " over budget"
        elif spent > budget * 0.8:
            remaining = round(budget - spent, 2)
            lines += "\n  Note: " + cat.title() + " has $" + str(remaining) + " remaining in budget"

    return lines.strip()


# ── Budget Management ─────────────────────────────────────────
def set_budget(category, amount):
    """Set a monthly budget for a category."""
    data = _load_data()
    data["budgets"][category.lower().strip()] = round(float(amount), 2)
    _save_data(data)
    return "Budget set: $" + str(round(float(amount), 2)) + "/month for " + category


def get_budgets():
    """Show all budgets and current spending against them."""
    data = _load_data()
    budgets = data.get("budgets", {})
    if not budgets:
        return "No budgets set, Sir. Say 'set budget for groceries to 500' to create one."

    month_start = datetime.date.today().replace(day=1).isoformat()
    month_expenses = [e for e in data["expenses"] if e["date"] >= month_start]
    categories = {}
    for e in month_expenses:
        cat = e["category"]
        categories[cat] = categories.get(cat, 0) + e["amount"]

    lines = "Monthly budgets:\n"
    for cat, budget in sorted(budgets.items()):
        spent = categories.get(cat, 0)
        remaining = budget - spent
        pct = int((spent / budget) * 100) if budget > 0 else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        status = " OVER" if remaining < 0 else ""
        lines += ("  " + cat.title() + ": $" + str(round(spent, 2))
                  + " / $" + str(round(budget, 2))
                  + " [" + bar + "] " + str(pct) + "%" + status + "\n")
    return lines.strip()


def remove_budget(category):
    """Remove a budget category."""
    data = _load_data()
    cat = category.lower().strip()
    if cat in data.get("budgets", {}):
        del data["budgets"][cat]
        _save_data(data)
        return "Budget removed for " + category
    return "No budget found for " + category


# ── Stock Watchlist ───────────────────────────────────────────
def get_stock_price(symbol):
    """Get current stock price using free API."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol.upper()
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            prev_close = meta.get("chartPreviousClose", price)
            change = price - prev_close
            pct = (change / prev_close * 100) if prev_close else 0
            direction = "up" if change >= 0 else "down"
            return {
                "symbol": symbol.upper(),
                "price": round(price, 2),
                "change": round(change, 2),
                "percent": round(pct, 2),
                "direction": direction
            }
    except:
        pass
    return None


def add_to_watchlist(symbol):
    """Add a stock to the watchlist."""
    data = _load_data()
    symbol = symbol.upper().strip()
    if symbol not in data["watchlist"]:
        # Verify the symbol exists
        info = get_stock_price(symbol)
        if info:
            data["watchlist"].append(symbol)
            _save_data(data)
            return ("Added " + symbol + " to watchlist. Currently at $"
                    + str(info["price"]) + " (" + info["direction"] + " "
                    + str(abs(info["percent"])) + "%)")
        return "Could not find stock symbol: " + symbol
    return symbol + " is already on your watchlist."


def remove_from_watchlist(symbol):
    """Remove a stock from the watchlist."""
    data = _load_data()
    symbol = symbol.upper().strip()
    if symbol in data["watchlist"]:
        data["watchlist"].remove(symbol)
        _save_data(data)
        return "Removed " + symbol + " from watchlist."
    return symbol + " is not on your watchlist."


def check_watchlist():
    """Check prices for all watchlist stocks."""
    data = _load_data()
    if not data["watchlist"]:
        return "Your watchlist is empty, Sir. Say 'watch AAPL' to add a stock."

    lines = "Stock watchlist:\n"
    for symbol in data["watchlist"]:
        info = get_stock_price(symbol)
        if info:
            arrow = "▲" if info["direction"] == "up" else "▼"
            lines += ("  " + info["symbol"] + ": $" + str(info["price"])
                      + " " + arrow + " " + str(abs(info["percent"])) + "%\n")
        else:
            lines += "  " + symbol + ": unavailable\n"
    return lines.strip()


def check_stock(symbol):
    """Check a single stock price."""
    info = get_stock_price(symbol)
    if info:
        arrow = "up" if info["direction"] == "up" else "down"
        return (info["symbol"] + " is at $" + str(info["price"])
                + ", " + arrow + " " + str(abs(info["percent"])) + "% today.")
    return "Could not find stock: " + symbol


# ── Intent Detection ──────────────────────────────────────────
def detect_finance_command(message):
    """Detect finance-related commands."""
    msg = message.lower().strip()

    # Add expense: "I spent 50 on groceries" or "spent $30 on food"
    spent_match = re.search(
        r'(?:i\s+)?spent\s+\$?(\d+\.?\d*)\s+(?:on|at|for)\s+(.+)', msg
    )
    if spent_match:
        amount = float(spent_match.group(1))
        rest = spent_match.group(2).strip()
        # Try to split category and description
        parts = rest.split(" for ", 1)
        if len(parts) == 2:
            return ("add_expense", (amount, parts[0], parts[1]))
        return ("add_expense", (amount, rest, ""))

    # Also match: "$50 groceries" or "50 dollars on food"
    quick_match = re.search(r'\$(\d+\.?\d*)\s+(?:on\s+)?(\w+)', msg)
    if quick_match and any(w in msg for w in ["spent", "paid", "bought", "cost"]):
        return ("add_expense", (float(quick_match.group(1)), quick_match.group(2), ""))

    # Spending summaries
    if any(w in msg for w in ["spending today", "spent today", "today's spending",
                               "todays spending"]):
        return ("spending_today", None)
    if any(w in msg for w in ["spending this week", "spent this week", "weekly spending",
                               "week's spending"]):
        return ("spending_week", None)
    if any(w in msg for w in ["spending this month", "spent this month", "monthly spending",
                               "month's spending", "how much have i spent"]):
        return ("spending_month", None)

    # Budgets
    budget_match = re.search(r'set\s+budget\s+(?:for\s+)?(\w+)\s+(?:to|at)\s+\$?(\d+)', msg)
    if budget_match:
        return ("set_budget", (budget_match.group(1), float(budget_match.group(2))))
    if any(w in msg for w in ["my budgets", "show budgets", "check budgets",
                               "budget status", "how are my budgets"]):
        return ("get_budgets", None)
    remove_budget_match = re.search(r'remove\s+budget\s+(?:for\s+)?(\w+)', msg)
    if remove_budget_match:
        return ("remove_budget", remove_budget_match.group(1))

    # Stock watchlist
    if any(w in msg for w in ["my watchlist", "check watchlist", "show watchlist",
                               "stock watchlist", "how are my stocks"]):
        return ("check_watchlist", None)

    watch_match = re.search(r'(?:watch|add|track)\s+([A-Za-z]{1,5})(?:\s|$)', msg)
    if watch_match and any(w in msg for w in ["watch", "track", "add to watchlist"]):
        return ("add_watchlist", watch_match.group(1))

    unwatch_match = re.search(r'(?:unwatch|remove|stop tracking)\s+([A-Za-z]{1,5})', msg)
    if unwatch_match:
        return ("remove_watchlist", unwatch_match.group(1))

    # Check specific stock
    stock_match = re.search(r'(?:price of|check|how is|how\'s|hows)\s+([A-Za-z]{1,5})(?:\s+stock)?', msg)
    if stock_match and any(w in msg for w in ["stock", "price", "trading", "share"]):
        return ("check_stock", stock_match.group(1))

    return (None, None)


def execute_finance_command(action, args):
    """Execute a finance command."""
    if action == "add_expense":
        amount, category, desc = args
        return add_expense(amount, category, desc)
    elif action == "spending_today":
        return get_spending_today()
    elif action == "spending_week":
        return get_spending_week()
    elif action == "spending_month":
        return get_spending_month()
    elif action == "set_budget":
        cat, amount = args
        return set_budget(cat, amount)
    elif action == "get_budgets":
        return get_budgets()
    elif action == "remove_budget":
        return remove_budget(args)
    elif action == "check_watchlist":
        return check_watchlist()
    elif action == "add_watchlist":
        return add_to_watchlist(args)
    elif action == "remove_watchlist":
        return remove_from_watchlist(args)
    elif action == "check_stock":
        return check_stock(args)
    return "Unknown finance command"
