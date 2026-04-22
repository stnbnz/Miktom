import routeros_api
import os
import sys
import django
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from django.utils import timezone
from dashboard.models import Router, TrackedDevice, ActivityLog

try:
    from alert import send_telegram_markdown
except ImportError:
    def send_telegram_markdown(msg): print("[alert] Not available:", msg)

print("================================")
print(" MikroTik Device Tracker")
print(f" Time: {datetime.now()}")
print("================================")

# Get active router from database
router = Router.objects.filter(is_active=True).first()
if not router:
    print("Error: No active router in database.")
    sys.exit(1)

ROUTER_IP = router.ip_address
USERNAME = router.username
PASSWORD = router.password

print(f"Tracking devices on: {router.name} ({ROUTER_IP})")

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=router.port,
        plaintext_login=True
    )
    api = connection.get_api()

    # Get active DHCP leases
    dhcp_api = api.get_resource('/ip/dhcp-server/lease')
    leases = dhcp_api.get()

    new_devices = []
    now = timezone.now()
    seen_macs = set()

    for lease in leases:
        mac = lease.get('mac-address')
        ip = lease.get('active-address', lease.get('address', 'Unknown IP'))
        hostname = lease.get('host-name', '') or 'Unknown Device'

        if not mac:
            continue

        seen_macs.add(mac)

        device, created = TrackedDevice.objects.get_or_create(
            router=router,
            mac_address=mac,
            defaults={
                'hostname': hostname,
                'ip_address': ip,
                'is_online': True
            }
        )

        if created:
            new_devices.append((mac, hostname, ip))
            print(f"  [+] New device: {hostname} ({ip}) — {mac}")

            ActivityLog.objects.create(
                router=router,
                activity_type='device_detected',
                description=f'New device detected: {hostname} ({ip})',
                metadata={
                    'mac_address': mac,
                    'ip_address': ip,
                    'hostname': hostname
                },
                success=True
            )
        else:
            # Update existing device — refresh IP, hostname, and mark online
            updated_fields = ['last_seen', 'is_online']
            device.is_online = True
            if ip and ip != 'Unknown IP':
                device.ip_address = ip
                updated_fields.append('ip_address')
            if hostname and hostname != 'Unknown Device' and device.hostname == 'Unknown Device':
                device.hostname = hostname
                updated_fields.append('hostname')
            device.save(update_fields=updated_fields)

    # Mark devices not in current lease as offline
    TrackedDevice.objects.filter(router=router, is_online=True).exclude(
        mac_address__in=seen_macs
    ).update(is_online=False)

    connection.disconnect()

    if new_devices:
        print(f"\n{len(new_devices)} new device(s) detected!")

        # Build Telegram notification for new devices
        device_lines = "\n".join(
            [f"• `{hostname}` — `{ip}` ({mac})" for mac, hostname, ip in new_devices]
        )
        alert_msg = (
            f"📡 *New Device(s) Detected*\n\n"
            f"Router: `{router.name}` ({ROUTER_IP})\n\n"
            f"{device_lines}"
        )
        send_telegram_markdown(alert_msg)
    else:
        print("No new devices detected.")

    print("Device tracking completed.")

except Exception as e:
    print(f"Error during device tracking: {e}")
    try:
        ActivityLog.objects.create(
            router=router,
            activity_type='device_detected',
            description='Device tracking failed',
            metadata={'error': str(e)},
            success=False,
            error_message=str(e)
        )
    except Exception as db_err:
        print(f"Also failed to log error to DB: {db_err}")
