"""
Alfred's Security Monitor
Detects unusual network connections, login events, and file changes.
"""
import psutil
import subprocess
import os
import time
import datetime
import json

SECURITY_LOG = os.path.expanduser("~/alfred_security.json")
WATCH_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
]

_known_connections = set()
_dir_snapshots = {}
_last_alerts = {}


def _load_log():
    if os.path.exists(SECURITY_LOG):
        with open(SECURITY_LOG, 'r') as f:
            return json.load(f)
    return {"alerts": []}


def _save_alert(alert_type, message):
    log = _load_log()
    log["alerts"].append({
        "type": alert_type,
        "message": message,
        "timestamp": datetime.datetime.now().isoformat()
    })
    # Keep last 50 alerts
    log["alerts"] = log["alerts"][-50:]
    with open(SECURITY_LOG, 'w') as f:
        json.dump(log, f, indent=2)


def check_network_connections():
    """Check for suspicious network connections."""
    global _known_connections
    alerts = []
    now = time.time()

    suspicious_ports = {4444, 5555, 1337, 31337, 6667, 6697}  # common malware ports
    
    current = set()
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'ESTABLISHED' and conn.raddr:
            key = (conn.raddr.ip, conn.raddr.port)
            current.add(key)
            
            # Check suspicious ports
            if conn.raddr.port in suspicious_ports:
                if "suspicious_port" not in _last_alerts or now - _last_alerts["suspicious_port"] > 3600:
                    try:
                        proc = psutil.Process(conn.pid)
                        proc_name = proc.name()
                    except:
                        proc_name = "unknown"
                    alert = ("Sir, I've detected a connection on port "
                             + str(conn.raddr.port) + " to " + conn.raddr.ip
                             + " from " + proc_name + ". This warrants investigation.")
                    alerts.append(alert)
                    _save_alert("suspicious_port", alert)
                    _last_alerts["suspicious_port"] = now

    # Detect new connections (first run builds baseline)
    if _known_connections:
        new_conns = current - _known_connections
        if len(new_conns) > 10:  # Burst of new connections
            if "conn_burst" not in _last_alerts or now - _last_alerts["conn_burst"] > 600:
                alert = ("Unusual network activity detected — "
                         + str(len(new_conns)) + " new connections in the last check.")
                alerts.append(alert)
                _save_alert("connection_burst", alert)
                _last_alerts["conn_burst"] = now

    _known_connections = current
    return alerts


def check_file_changes():
    """Monitor important directories for unexpected changes."""
    global _dir_snapshots
    alerts = []
    now = time.time()

    for dir_path in WATCH_DIRS:
        if not os.path.exists(dir_path):
            continue

        try:
            current_files = set(os.listdir(dir_path))
        except:
            continue

        dir_name = os.path.basename(dir_path)
        
        if dir_path in _dir_snapshots:
            old_files = _dir_snapshots[dir_path]
            new_files = current_files - old_files
            deleted_files = old_files - current_files

            # Check for suspicious new executables
            for f in new_files:
                if f.endswith(('.exe', '.bat', '.cmd', '.ps1', '.vbs', '.scr')):
                    if "new_exe" not in _last_alerts or now - _last_alerts["new_exe"] > 300:
                        alert = ("Sir, a new executable appeared in " + dir_name
                                 + ": " + f + ". I'd recommend verifying its origin.")
                        alerts.append(alert)
                        _save_alert("new_executable", alert)
                        _last_alerts["new_exe"] = now

            # Large number of deletions
            if len(deleted_files) > 10:
                if "mass_delete" not in _last_alerts or now - _last_alerts["mass_delete"] > 600:
                    alert = (str(len(deleted_files)) + " files were removed from "
                             + dir_name + ". This may warrant attention.")
                    alerts.append(alert)
                    _save_alert("mass_deletion", alert)
                    _last_alerts["mass_delete"] = now

        _dir_snapshots[dir_path] = current_files

    return alerts


def get_active_connections():
    """List current network connections grouped by process."""
    connections = {}
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'ESTABLISHED' and conn.raddr:
            try:
                proc = psutil.Process(conn.pid)
                name = proc.name()
            except:
                name = "unknown"
            if name not in connections:
                connections[name] = []
            connections[name].append(conn.raddr.ip + ":" + str(conn.raddr.port))

    if not connections:
        return "No active network connections."

    lines = "Active connections:\n"
    for name, addrs in sorted(connections.items()):
        lines += "  " + name + ": " + str(len(addrs)) + " connections\n"
    return lines.strip()


def get_security_log():
    """Show recent security alerts."""
    log = _load_log()
    if not log["alerts"]:
        return "No security alerts recorded, Sir. All clear."
    lines = "Recent security alerts:\n"
    for a in log["alerts"][-5:]:
        lines += "  " + a["timestamp"][:16] + " — " + a["message"][:60] + "\n"
    return lines.strip()


def run_security_scan():
    """Run a comprehensive security check."""
    results = ["Security scan results:"]

    # Open ports
    listening = []
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'LISTEN':
            listening.append(str(conn.laddr.port))
    results.append("  Open ports: " + (", ".join(listening[:10]) if listening else "none"))

    # Active connections count
    established = sum(1 for c in psutil.net_connections(kind='inet') if c.status == 'ESTABLISHED')
    results.append("  Active connections: " + str(established))

    # Running processes count
    proc_count = len(list(psutil.process_iter()))
    results.append("  Running processes: " + str(proc_count))

    # User accounts
    users = psutil.users()
    results.append("  Active sessions: " + str(len(users)))

    # Uptime
    boot = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot
    results.append("  System uptime: " + str(uptime).split('.')[0])

    results.append("  Status: All clear" if not _load_log()["alerts"] else "  Status: Review alerts")
    return "\n".join(results)


def check_all_security():
    """Run all security checks. Returns list of alerts."""
    alerts = []
    alerts.extend(check_network_connections())
    alerts.extend(check_file_changes())
    return alerts


# ── Intent Detection ──────────────────────────────────────────
def detect_security_command(message):
    msg = message.lower().strip()

    if any(w in msg for w in ["security scan", "run security", "security check",
                               "scan my computer", "is my computer secure",
                               "security status"]):
        return ("scan", None)

    if any(w in msg for w in ["network connections", "active connections",
                               "whos connected", "who's connected"]):
        return ("connections", None)

    if any(w in msg for w in ["security alerts", "security log", "any threats",
                               "any security issues"]):
        return ("log", None)

    return (None, None)


def execute_security_command(action, args):
    if action == "scan":
        return run_security_scan()
    elif action == "connections":
        return get_active_connections()
    elif action == "log":
        return get_security_log()
    return "Unknown security command"
