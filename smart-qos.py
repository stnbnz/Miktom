import routeros_api
import subprocess
import json
import os
from datetime import datetime

# ======================
# ROUTER CONFIG
# ======================

ROUTER_IP = "192.168.88.1"
USERNAME = "admin"
PASSWORD = ""

# ======================
# QoS CONFIG
# ======================

# Target Queue to throttle when main connection is saturated
QUEUE_NAME = "WiFi-Guest" 
NORMAL_LIMIT = "10M/10M"
THROTTLED_LIMIT = "2M/2M"

# Interface to monitor for total saturation
WAN_INTERFACE = "ether1"
# Max-Tx & Max-Rx limits in Mbps to trigger throttle
SATURATION_THRESHOLD_MBPS = 45 

STATE_FILE = "qos_state.json"

print("================================")
print(" MikroTik Smart QoS Manager")
print(" Time:", datetime.now())
print("================================")

# Load State
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {"is_throttled": False}

def send_alert(message):
    print("SENDING ALERT:", message)
    subprocess.run([
        "python3",
        "alert.py",
        message
    ])

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
