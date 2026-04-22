import requests
from datetime import datetime

TOKEN = "8640327346:AAFK6fxfANUYPm2UvsAU2mX_DCIRCDBH2Og"
CHAT_ID = "8663572939"

def _send(message, parse_mode=None):
    """Internal function to send a message via Telegram."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, data=payload, timeout=10)
        result = response.json()
        if not result.get("ok"):
            print(f"[Telegram] Error: {result.get('description', 'Unknown error')}")
        return result
    except Exception as e:
        print(f"[Telegram] Exception: {e}")
        return None


def send_telegram(message):
    """Send a plain text alert notification via Telegram."""
    full_message = (
        f"🚨 MikroTik Network Alert\n\n"
        f"{message}\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return _send(full_message)


def send_telegram_markdown(message):
    """Send a formatted Markdown message via Telegram.
    
    Use *bold*, _italic_, `code` etc. in the message.
    NOTE: Special characters like (, ), ., -, _, *, ~ must be escaped in MarkdownV2.
    This function uses legacy Markdown (v1) which is more lenient.
    """
    return _send(message, parse_mode="Markdown")


def send_alert_info(title, body):
    """Send a structured info alert (plain text) with title and body."""
    message = (
        f"ℹ️ *{title}*\n\n"
        f"{body}\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return _send(message, parse_mode="Markdown")


def send_alert_warning(title, body):
    """Send a structured warning alert (Markdown) with title and body."""
    message = (
        f"⚠️ *{title}*\n\n"
        f"{body}\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return _send(message, parse_mode="Markdown")


def send_alert_critical(title, body):
    """Send a structured critical alert (Markdown) with title and body."""
    message = (
        f"🔴 *CRITICAL: {title}*\n\n"
        f"{body}\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return _send(message, parse_mode="Markdown")
