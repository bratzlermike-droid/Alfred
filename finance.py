"""
Alfred's Email Manager
Read, search, summarize, and compose Gmail via IMAP/SMTP.
"""
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import os
import re
import datetime

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

_gmail_address = ""
_gmail_password = ""


def _load_credentials():
    global _gmail_address, _gmail_password
    if _gmail_address:
        return
    config = os.path.expanduser("~/chief_config.txt")
    if os.path.exists(config):
        with open(config) as f:
            for line in f:
                if line.startswith("GMAIL_ADDRESS="):
                    _gmail_address = line.strip().split("=", 1)[1]
                elif line.startswith("GMAIL_APP_PASSWORD="):
                    _gmail_password = line.strip().split("=", 1)[1]


def _decode_subject(subject):
    """Decode email subject header."""
    if not subject:
        return "(no subject)"
    decoded = decode_header(subject)
    parts = []
    for part, encoding in decoded:
        if isinstance(part, bytes):
            parts.append(part.decode(encoding or 'utf-8', errors='replace'))
        else:
            parts.append(part)
    return " ".join(parts)


def _decode_body(msg):
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode('utf-8', errors='replace')
        except:
            pass
    return "(could not read body)"


def get_recent_emails(count=5, unread_only=False):
    """Fetch recent emails."""
    _load_credentials()
    if not _gmail_address:
        return "Gmail not configured. Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to chief_config.txt"

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(_gmail_address, _gmail_password)
        mail.select("INBOX")

        if unread_only:
            status, messages = mail.search(None, "UNSEEN")
        else:
            status, messages = mail.search(None, "ALL")

        if status != "OK" or not messages[0]:
            mail.logout()
            return "No emails found." if not unread_only else "No unread emails, Sir."

        msg_ids = messages[0].split()
        latest = msg_ids[-count:]
        latest.reverse()

        results = []
        for msg_id in latest:
            status, data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])
            sender = msg.get("From", "unknown")
            # Clean sender
            if "<" in sender:
                name = sender.split("<")[0].strip().strip('"')
                if not name:
                    name = sender.split("<")[1].split(">")[0]
            else:
                name = sender
            subject = _decode_subject(msg.get("Subject"))
            date = msg.get("Date", "")

            results.append({
                "id": msg_id.decode(),
                "from": name[:30],
                "subject": subject[:60],
                "date": date[:20],
            })

        mail.logout()

        if not results:
            return "No emails found."

        lines = "Recent emails:\n"
        for i, r in enumerate(results, 1):
            lines += "  " + str(i) + ". " + r["from"] + " — " + r["subject"] + "\n"
        return lines.strip()

    except imaplib.IMAP4.error as e:
        return "Gmail login failed. Check your app password, Sir."
    except Exception as e:
        return "Email error: " + str(e)


def get_unread_count():
    """Get count of unread emails."""
    _load_credentials()
    if not _gmail_address:
        return 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(_gmail_address, _gmail_password)
        mail.select("INBOX")
        status, messages = mail.search(None, "UNSEEN")
        mail.logout()
        if status == "OK" and messages[0]:
            return len(messages[0].split())
        return 0
    except:
        return 0


def read_email(index=1):
    """Read a specific email by index (most recent first)."""
    _load_credentials()
    if not _gmail_address:
        return "Gmail not configured."

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(_gmail_address, _gmail_password)
        mail.select("INBOX")

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            mail.logout()
            return "No emails found."

        msg_ids = messages[0].split()
        target = msg_ids[-(index)]

        status, data = mail.fetch(target, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        sender = msg.get("From", "unknown")
        subject = _decode_subject(msg.get("Subject"))
        body = _decode_body(msg)

        mail.logout()

        # Truncate body
        if len(body) > 500:
            body = body[:500] + "..."

        return ("From: " + sender + "\nSubject: " + subject
                + "\n\n" + body)

    except Exception as e:
        return "Error reading email: " + str(e)


def search_emails(query, count=5):
    """Search emails by subject or sender."""
    _load_credentials()
    if not _gmail_address:
        return "Gmail not configured."

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(_gmail_address, _gmail_password)
        mail.select("INBOX")

        # Search by subject and from
        status, messages = mail.search(None, '(OR SUBJECT "' + query + '" FROM "' + query + '")')

        if status != "OK" or not messages[0]:
            mail.logout()
            return "No emails matching '" + query + "' found."

        msg_ids = messages[0].split()
        latest = msg_ids[-count:]
        latest.reverse()

        results = []
        for msg_id in latest:
            status, data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])
            sender = msg.get("From", "unknown")
            if "<" in sender:
                name = sender.split("<")[0].strip().strip('"')
                if not name:
                    name = sender.split("<")[1].split(">")[0]
            else:
                name = sender
            subject = _decode_subject(msg.get("Subject"))
            results.append(name[:25] + " — " + subject[:50])

        mail.logout()

        if not results:
            return "No results for '" + query + "'."
        return "Emails matching '" + query + "':\n  " + "\n  ".join(results)

    except Exception as e:
        return "Search error: " + str(e)


def send_email(to_address, subject, body):
    """Send an email."""
    _load_credentials()
    if not _gmail_address:
        return "Gmail not configured."

    try:
        msg = MIMEMultipart()
        msg["From"] = _gmail_address
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(_gmail_address, _gmail_password)
        server.send_message(msg)
        server.quit()

        return "Email sent to " + to_address
    except Exception as e:
        return "Send error: " + str(e)


# ── Intent Detection ──────────────────────────────────────────
def detect_email_command(message):
    """Detect email-related commands."""
    msg = message.lower().strip()

    # Check emails
    if any(w in msg for w in ["check my email", "check my mail", "any emails",
                               "any new emails", "unread emails", "check emails",
                               "check inbox", "my inbox", "any mail",
                               "important emails", "new messages"]):
        if any(w in msg for w in ["unread", "new", "important"]):
            return ("unread", None)
        return ("recent", None)

    # Read specific email
    read_match = re.search(r'read (?:email|message) (?:number )?(\d+)', msg)
    if read_match:
        return ("read", int(read_match.group(1)))
    if any(w in msg for w in ["read the first", "read the latest", "read my latest"]):
        return ("read", 1)
    if "read the second" in msg:
        return ("read", 2)
    if "read the third" in msg:
        return ("read", 3)

    # Search
    search_match = re.search(r'(?:search|find|look for) (?:emails?|mail) (?:from|about|regarding) (.+)', msg)
    if search_match:
        return ("search", search_match.group(1).strip())

    # Send email
    if any(msg.startswith(w) for w in ["send email", "send an email", "compose email",
                                        "write an email", "email "]):
        return ("compose", msg)

    # Unread count
    if any(w in msg for w in ["how many emails", "how many unread",
                               "email count", "unread count"]):
        return ("count", None)

    return (None, None)


def execute_email_command(action, args):
    """Execute an email command."""
    if action == "recent":
        return get_recent_emails(5)
    elif action == "unread":
        return get_recent_emails(5, unread_only=True)
    elif action == "read":
        return read_email(args)
    elif action == "search":
        return search_emails(args)
    elif action == "count":
        count = get_unread_count()
        if count == 0:
            return "Your inbox is clear, Sir. No unread emails."
        return "You have " + str(count) + " unread email" + ("s" if count != 1 else "") + ", Sir."
    elif action == "compose":
        return "To send an email, say: 'Send email to person@email.com subject Hello body Your message here'"
    return "Unknown email command"
