import os
import sys
import django
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import Router
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


def run_rogue_detection():
    print(f"[{datetime.now()}] Running Rogue Device & DHCP Detection...")
    routers = Router.objects.all()
    if not routers.exists():
        print("  No routers configured.")
        return
        
    for router in routers:
        print(f"  Checking Router: {router.name} ({router.ip_address})")
        try:
            conn, api = _get_mikrotik_api(router)
            
            # 1. ROGUE DHCP DETECTION
            try:
                # Assuming setting up DHCP Alert in MikroTik first: /ip dhcp-server alert add interface=bridge valid-server=mac_of_legitimate
                # Alternatively, check log for dhcp alert messages
                logs = api.get_resource('/log').get()
                rogue_logs = [log for log in logs if 'dhcp' in log.get('topics', '') and 'alert' in log.get('topics', '')]
                
                # Check for unexpected DHCP server discoveries from logs within the last hour
                for log in rogue_logs[-5:]:
                    msg = log.get('message', '')
                    if 'rogue dhcp' in msg.lower() or 'unknown dhcp' in msg.lower():
                        alert_msg = f"🚨 *SECURITY ALERT*: Rogue DHCP Server detected on {router.name}!\nDetails: {msg}"
                        print(f"    {alert_msg}")
                        send_telegram_markdown(alert_msg)
            except Exception as e:
                print(f"    Could not fetch logs for Rogue DHCP: {e}")
            
            # 2. ROGUE DEVICE/MAC ADDRESS DETECTION (Unregistered Static IP)
            # Find devices trying to bypass Hotspot/PPPoE
            try:
                arp_entries = api.get_resource('/ip/arp').get()
                # Assuming known devices are static or bound. We could trigger alerts for Unknown IPs.
                # Here we just alert if ARP table grows unusually high, indicating potential anomaly
                if len(arp_entries) > 500: # Threshold example
                    alert_msg = f"⚠️ *WARNING*: Unusually high ARP entries ({len(arp_entries)}) on {router.name}. Potential MAC address spoofing or ARP storm."
                    send_telegram_markdown(alert_msg)
            except Exception as e:
                pass
                
            conn.disconnect()
        except Exception as e:
            print(f"  Error processing router {router.name}: {e}")


if __name__ == "__main__":
    run_rogue_detection()
