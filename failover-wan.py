import routeros_api
import subprocess
import os
import json
from datetime import datetime

# ======================
# ROUTER CONFIG
# ======================

ROUTER_IP = "192.168.88.1"
USERNAME = "admin"
PASSWORD = "1945"

# ======================
# FAILOVER CONFIG
# ======================

# Target IP to ping to check internet (e.g., Google DNS)
PING_TARGET_1 = "8.8.8.8"
PING_TARGET_2 = "1.1.1.1"

# The names/comments or existing routes for ISP 1 and ISP 2.
# In MikroTik, we identify routes by their "comment" field.
ISP1_ROUTE_COMMENT = "ISP1_MAIN"
ISP2_ROUTE_COMMENT = "ISP2_BACKUP"

STATE_FILE = "failover_state.json"

print("================================")
print(" MikroTik WAN Failover Guardian")
print(" Time:", datetime.now())
print("================================")

# Load State
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    # State values: "ISP1_ACTIVE", "ISP2_ACTIVE"
    state = {"active_wan": "ISP1_ACTIVE"}

def send_alert(message):
    print("SENDING ALERT:", message)
    subprocess.run([
        "python3",
        "alert.py",
        message
    ])

# Check internet directly via Ping from this script 
# (Assuming the script runs on a machine behind the router that routes to internet)
def check_internet():
    # Ping 8.8.8.8
    p1 = subprocess.run(["ping", "-c", "2", "-W", "2", PING_TARGET_1], stdout=subprocess.DEVNULL)
    # Ping 1.1.1.1
    p2 = subprocess.run(["ping", "-c", "2", "-W", "2", PING_TARGET_2], stdout=subprocess.DEVNULL)
    
    # Return true if any of the pings succeed
    return p1.returncode == 0 or p2.returncode == 0

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()

    # Get routing table
    routes_api = api.get_resource('/ip/route')
    all_routes = routes_api.get()
    
    isp1_route = next((r for r in all_routes if r.get('comment') == ISP1_ROUTE_COMMENT), None)
    isp2_route = next((r for r in all_routes if r.get('comment') == ISP2_ROUTE_COMMENT), None)

    if not isp1_route or not isp2_route:
        print(f"Warning: Cannot find routes with comments '{ISP1_ROUTE_COMMENT}' and '{ISP2_ROUTE_COMMENT}' in RouterOS.")
        # We can't manage failover if we don't know the routes
    else:
        internet_up = check_internet()
        
        if state["active_wan"] == "ISP1_ACTIVE":
            if not internet_up:
                print("ISP1 appears to be DOWN. Failing over to ISP2...")
                # Increase ISP1 distance above ISP2 to make ISP2 preferred
                # Typical setups: ISP1 distance 1, ISP2 distance 2.
                # Failover setup: ISP1 distance 3, ISP2 distance 2.
                routes_api.set(id=isp1_route['.id'], distance="3")
                state["active_wan"] = "ISP2_ACTIVE"
                
                alert_msg = "🔄 *WAN FAILOVER TRIGGERED*\n\n"
                alert_msg += "ISP 1 (Main) is DOWN! 🔴\n"
                alert_msg += "Traffic has been automatically shifted to ISP 2 (Backup) 🟢."
                send_alert(alert_msg)
            else:
                print("ISP1 is UP and active. No action needed.")
                
        elif state["active_wan"] == "ISP2_ACTIVE":
            if internet_up:
                # Need to test if ISP1 is actually back up. Or simply test by bringing it back to priority and checking.
                # A safer way in MikroTik is Netwatch, but for this script we will periodically try to restore ISP1.
                print("Attempting to restore ISP1 as main WAN...")
                routes_api.set(id=isp1_route['.id'], distance="1")
                
                # Check internet immediately after switching back
                import time
                time.sleep(5) # Wait for routing to settle
                
                if check_internet():
                    print("ISP1 restoration successful. ISP1 is UP.")
                    state["active_wan"] = "ISP1_ACTIVE"
                    
                    alert_msg = "✅ *PRIMARY WAN RESTORED*\n\n"
                    alert_msg += "ISP 1 (Main) is back ONLINE! 🟢\n"
                    alert_msg += "Traffic has been shifted back to the primary link."
                    send_alert(alert_msg)
                else:
                    print("ISP1 still down. Reverting to ISP2.")
                    routes_api.set(id=isp1_route['.id'], distance="3")
            else:
                print("Both ISP1 and ISP2 appear to be down. Total outage.")

    connection.disconnect()
    
    # Save State
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)
        
    print("Failover check completed.")

except Exception as e:
    print("Error:", e)
