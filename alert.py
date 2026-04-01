import requests
from datetime import datetime

TOKEN = "8640327346:AAEJcsGCRpXyDDG_ylSQP0X8yQaz7GdxeUg"
CHAT_ID = "8663572939"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": (
            f"🚨 MikroTik Network Alert\n\n"
            f"{message}\n\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        print("Telegram:", response.text)
    except Exception as e:
        print("Telegram error:", e)
