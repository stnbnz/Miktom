import routeros_api
import os
import sys
import django
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from web_monitor.dashboard.models import Router, TrackedDevice, ActivityLog

print("================================")
print(" MikroTik Device Tracker")
print(" Time:", datetime.now())
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
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()

    # Get active DHCP leases
    dhcp_api = api.get_resource('/ip/dhcp-server/lease')
    leases = dhcp_api.get()
    
    new_devices = []
    now = datetime.now()

    for lease in leases:
        mac = lease.get('mac-address')
        # Address can be under 'address' or 'active-address'
        ip = lease.get('active-address', lease.get('address', 'Unknown IP'))
        hostname = lease.get('host-name', 'Unknown Device')
        
        if mac:
            # Check if device is already in database
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
                print(f"✓ New device detected: {hostname} ({ip}) - {mac}")
                
                # Log activity
                ActivityLog.objects.create(
                    router=router,
                    activity_type='device_detected',
                    description=f'New device detected: {hostname}',
                    metadata={
                        'mac_address': mac,
                        'ip_address': ip,
                        'hostname': hostname
                    },
                    success=True
                )
            else:
                # Update last seen
                device.last_seen = now
                device.is_online = True
                device.save(update_fields=['last_seen', 'is_online'])

    connection.disconnect()

    if new_devices:
        print(f"\nDetected {len(new_devices)} new device(s)")
    else:
        print("No new devices detected.")
        
    print("Device tracking completed.")

except Exception as e:
    print(f"Error: {e}")
    ActivityLog.objects.create(
        router=router,
        activity_type='device_detected',
        description='Device tracking failed',
        metadata={'error': str(e)},
        success=False,
        error_message=str(e)
    )

except Exception as e:
    print("Error:", e)
