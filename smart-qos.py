import routeros_api
import sys
import os
import django
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import Router, ActivityLog, QoSState, QoSEvent
from alert import send_telegram_markdown

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
print(f" Time: {datetime.now()}")
print(f" Router: {router.name} ({ROUTER_IP})")
print("================================")

# Get current QoS state from database
qos_state, _ = QoSState.objects.get_or_create(
    router=router,
    defaults={'is_throttled': False}
)
is_throttled = qos_state.is_throttled

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=router.port,
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
        try:
            traffic = monitor_api.call('monitor-traffic', {'interface': WAN_INTERFACE, 'once': ''})[0]
        except Exception as e:
            print(f"Warning: Could not get traffic for {WAN_INTERFACE}: {e}")
            traffic = {}

        rx_bps = int(traffic.get('rx-bits-per-second', 0))
        tx_bps = int(traffic.get('tx-bits-per-second', 0))

        rx_mbps = rx_bps / 1_000_000
        tx_mbps = tx_bps / 1_000_000

        print(f"Traffic on {WAN_INTERFACE}: RX {rx_mbps:.2f} Mbps | TX {tx_mbps:.2f} Mbps")

        is_saturated = (rx_mbps > SATURATION_THRESHOLD_MBPS) or (tx_mbps > SATURATION_THRESHOLD_MBPS)

        if is_saturated:
            if not is_throttled:
                print(f"Network saturated! Activating QoS on '{QUEUE_NAME}'...")
                queue_api.set(id=target_queue['.id'], **{'max-limit': THROTTLED_LIMIT})

                # Update state in DB
                qos_state.is_throttled = True
                qos_state.save()

                QoSEvent.objects.create(
                    router=router,
                    event_type='throttled',
                    rx_mbps=rx_mbps,
                    tx_mbps=tx_mbps,
                    queue_name=QUEUE_NAME,
                    limit_applied=THROTTLED_LIMIT,
                    detail=f'Saturation threshold ({SATURATION_THRESHOLD_MBPS} Mbps) exceeded'
                )

                alert_msg = (
                    f"📉 *SMART QoS ACTIVATED*\n\n"
                    f"Network traffic exceeded {SATURATION_THRESHOLD_MBPS} Mbps on `{WAN_INTERFACE}`\n"
                    f"• RX: `{rx_mbps:.2f} Mbps`\n"
                    f"• TX: `{tx_mbps:.2f} Mbps`\n\n"
                    f"Guest WiFi has been throttled to `{THROTTLED_LIMIT}`"
                )
                send_telegram_markdown(alert_msg)

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

                # Update state in DB
                qos_state.is_throttled = False
                qos_state.save()

                QoSEvent.objects.create(
                    router=router,
                    event_type='restored',
                    rx_mbps=rx_mbps,
                    tx_mbps=tx_mbps,
                    queue_name=QUEUE_NAME,
                    limit_applied=NORMAL_LIMIT,
                    detail='Traffic normalized, throttle removed'
                )

                alert_msg = (
                    f"📈 *SMART QoS DEACTIVATED*\n\n"
                    f"Network traffic normalized on `{WAN_INTERFACE}`\n"
                    f"• RX: `{rx_mbps:.2f} Mbps`\n"
                    f"• TX: `{tx_mbps:.2f} Mbps`\n\n"
                    f"Guest WiFi restored to `{NORMAL_LIMIT}`"
                )
                send_telegram_markdown(alert_msg)

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
    print("QoS check completed successfully.")

except Exception as e:
    print(f"Error during QoS check: {e}")
    try:
        ActivityLog.objects.create(
            router=router,
            activity_type='qos_change',
            description='Smart QoS check failed',
            metadata={'error': str(e)},
            success=False,
            error_message=str(e)
        )
    except Exception as db_err:
        print(f"Also failed to log error to DB: {db_err}")
