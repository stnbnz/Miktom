import routeros_api
import sys
import os
import django
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from web_monitor.dashboard.models import Router, ActivityLog
from alert import send_telegram

# ======================
# ROUTER CONFIG
# ======================

router = Router.objects.filter(is_active=True).first()
if not router:
    print("Error: No active router in database.")
    sys.exit(1)

ROUTER_IP = router.ip_address
USERNAME = router.username
PASSWORD = router.password

# ======================
# QoS CONFIG
# ======================

QUEUE_NAME = "WiFi-Guest" 
NORMAL_LIMIT = "10M/10M"
THROTTLED_LIMIT = "2M/2M"

WAN_INTERFACE = "ether1"
SATURATION_THRESHOLD_MBPS = 45 

print("================================")
print(" MikroTik Smart QoS Manager")
print(" Time:", datetime.now())
print(f" Router: {router.name} ({ROUTER_IP})")
print("================================")

# Get current QoS state from database (use latest ActivityLog with qos_change)
latest_qos = ActivityLog.objects.filter(
    router=router,
    activity_type='qos_change'
).order_by('-timestamp').first()

is_throttled = False
if latest_qos and latest_qos.metadata:
    is_throttled = latest_qos.metadata.get('is_throttled', False)

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()

    # Get Queue
    queue_api = api.get_resource('/queue/simple')
    queues = queue_api.get()
    
    target_queue = next((q for q in queues if q.get('name') == QUEUE_NAME), None)

    if not target_queue:
        print(f"Warning: Queue named '{QUEUE_NAME}' not found. Cannot perform Smart QoS.")
    else:
        # Get interface traffic
        monitor_api = api.get_resource('/interface')
        traffic = monitor_api.call('monitor-traffic', {'interface': WAN_INTERFACE, 'once': ''})[0]
        
        rx_bps = int(traffic.get('rx-bits-per-second', 0))
        tx_bps = int(traffic.get('tx-bits-per-second', 0))
        
        rx_mbps = rx_bps / 1_000_000
        tx_mbps = tx_bps / 1_000_000
        
        print(f"Current traffic on {WAN_INTERFACE}: RX {rx_mbps:.2f} Mbps, TX {tx_mbps:.2f} Mbps")
        
        is_saturated = (rx_mbps > SATURATION_THRESHOLD_MBPS) or (tx_mbps > SATURATION_THRESHOLD_MBPS)
        
        if is_saturated:
            if not is_throttled:
                print(f"Network saturated. Activating QoS on '{QUEUE_NAME}'...")
                queue_api.set(id=target_queue['.id'], **{'max-limit': THROTTLED_LIMIT})
                is_throttled = True
                
                alert_msg = f"📉 *SMART QoS ACTIVATED*\n\nNetwork traffic high on {WAN_INTERFACE}!\nGuest WiFi limited to {THROTTLED_LIMIT}"
                send_telegram(alert_msg)
                
                ActivityLog.objects.create(
                    router=router,
                    activity_type='qos_change',
                    description=f'Smart QoS activated: {QUEUE_NAME} limited to {THROTTLED_LIMIT}',
                    metadata={
                        'queue': QUEUE_NAME,
                        'limit': THROTTLED_LIMIT,
                        'is_throttled': True,
                        'rx_mbps': rx_mbps,
                        'tx_mbps': tx_mbps
                    },
                    success=True
                )
            else:
                print("Network remains saturated. QoS still active.")
        else:
            if is_throttled:
                print(f"Network stable. Deactivating QoS on '{QUEUE_NAME}'...")
                queue_api.set(id=target_queue['.id'], **{'max-limit': NORMAL_LIMIT})
                is_throttled = False
                
                alert_msg = f"📈 *SMART QoS DEACTIVATED*\n\nNetwork traffic stable.\nGuest WiFi restored to {NORMAL_LIMIT}"
                send_telegram(alert_msg)
                
                ActivityLog.objects.create(
                    router=router,
                    activity_type='qos_change',
                    description=f'Smart QoS deactivated: {QUEUE_NAME} restored to {NORMAL_LIMIT}',
                    metadata={
                        'queue': QUEUE_NAME,
                        'limit': NORMAL_LIMIT,
                        'is_throttled': False,
                        'rx_mbps': rx_mbps,
                        'tx_mbps': tx_mbps
                    },
                    success=True
                )
            else:
                print("Network optimal. No QoS changes needed.")

    connection.disconnect()
    print("QoS check completed successfully")

except Exception as e:
    print(f"Error: {e}")
    ActivityLog.objects.create(
        router=router,
        activity_type='qos_change',
        description='Smart QoS check failed',
        metadata={'error': str(e)},
        success=False,
        error_message=str(e)
    )

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()

    # Get Queue
    queue_api = api.get_resource('/queue/simple')
    queues = queue_api.get()
    
    target_queue = next((q for q in queues if q.get('name') == QUEUE_NAME), None)

    if not target_queue:
        print(f"Warning: Queue named '{QUEUE_NAME}' not found. Cannot perform Smart QoS.")
    else:
        # Get interface traffic
        monitor_api = api.get_resource('/interface')
        # We must use monitor-traffic. Note: This is an active command, we need to gather 1 sample.
        # This requires raw api syntax for monitor-traffic.
        traffic = monitor_api.call('monitor-traffic', {'interface': WAN_INTERFACE, 'once': ''})[0]
        
        rx_bps = int(traffic.get('rx-bits-per-second', 0))
        tx_bps = int(traffic.get('tx-bits-per-second', 0))
        
        rx_mbps = rx_bps / 1_000_000
        tx_mbps = tx_bps / 1_000_000
        
        print(f"Current traffic on {WAN_INTERFACE}: RX {rx_mbps:.2f} Mbps, TX {tx_mbps:.2f} Mbps")
        
        is_saturated = (rx_mbps > SATURATION_THRESHOLD_MBPS) or (tx_mbps > SATURATION_THRESHOLD_MBPS)
        
        if is_saturated:
            if not state["is_throttled"]:
                print(f"Network is saturated (> {SATURATION_THRESHOLD_MBPS} Mbps). Activating QoS Throttling on '{QUEUE_NAME}'...")
                queue_api.set(id=target_queue['.id'], **{'max-limit': THROTTLED_LIMIT})
                state["is_throttled"] = True
                
                alert_msg = "📉 *SMART QoS ACTIVATED*\n\n"
                alert_msg += f"Network traffic is high on {WAN_INTERFACE}!\n"
                alert_msg += f"Guest WiFi bandwidth has been temporarily limited to {THROTTLED_LIMIT}."
                send_alert(alert_msg)
            else:
                print("Network remains saturated. QoS Throttling still active.")
        else:
            if state["is_throttled"]:
                print(f"Network traffic stabilized. Deactivating QoS Throttling on '{QUEUE_NAME}'...")
                queue_api.set(id=target_queue['.id'], **{'max-limit': NORMAL_LIMIT})
                state["is_throttled"] = False
                
                alert_msg = "📈 *SMART QoS DEACTIVATED*\n\n"
                alert_msg += f"Network traffic is stable.\n"
                alert_msg += f"Guest WiFi bandwidth restored to {NORMAL_LIMIT}."
                send_alert(alert_msg)
            else:
                print("Network traffic is optimal. No QoS changes required.")

    connection.disconnect()
    
    # Save State
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)
        
    print("QoS check completed.")

except Exception as e:
    print("Error:", e)
