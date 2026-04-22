import os
import sys
import django
from datetime import datetime
from django.utils import timezone

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import Router, Voucher, ActiveUser, ActivityLog
import routeros_api

try:
    from alert import send_telegram_markdown, send_telegram
except ImportError:
    def send_telegram_markdown(msg): print("[alert] Not available:", msg)
    def send_telegram(msg): print("[alert] Not available:", msg)

def _get_mikrotik_api(router):
    connection = routeros_api.RouterOsApiPool(
        router.ip_address,
        username=router.username,
        password=router.password,
        port=router.port,
        plaintext_login=True
    )
    return connection, connection.get_api()

def run_auto_suspend():
    print(f"[{datetime.now()}] Running Auto-Suspend Automation...")
    routers = Router.objects.all()
    if not routers.exists():
        print("  No routers configured.")
        return
        
    for router in routers:
        print(f"  Checking Router: {router.name} ({router.ip_address})")
        try:
            conn, api = _get_mikrotik_api(router)
            
            # 1. KICK EXPIRED HOTSPOT VOUCHERS
            expired_vouchers = Voucher.objects.filter(expires_at__lte=timezone.now())
            expired_codes = set([v.code for v in expired_vouchers])
            
            if expired_codes:
                active_hs = api.get_resource('/ip/hotspot/active').get()
                kicked_count = 0
                for hs in active_hs:
                    if hs.get('user') in expired_codes:
                        api.get_resource('/ip/hotspot/active').remove(id=hs.get('.id'))
                        kicked_count += 1
                        print(f"    Disabled/Kicked expired user: {hs.get('user')}")
                
                if kicked_count > 0:
                    msg = f"🛡️ *AUTO-SUSPEND*: Kicked {kicked_count} expired Hotspot users on {router.name}"
                    print(f"    {msg}")
                    send_telegram_markdown(msg)
            
            # FUTURE EXPANSION:
            # 2. DISABLE EXPIRED PPPoE (If using local DB for PPPoE billing)
            # Currently relying on MikroTik's native Radius/Profile uptime limits
            # But this script can be expanded here to handle DB-based PPPoE expiration.
            
            conn.disconnect()
        except Exception as e:
            print(f"  Error processing router {router.name}: {e}")

if __name__ == "__main__":
    run_auto_suspend()
