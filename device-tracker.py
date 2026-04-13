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
PASSWORD = "1945"

# ======================
# TRACKER CONFIG
# ======================
STATE_FILE = "known_devices.json"

print("================================")
print(" MikroTik Device Tracker")
print(" Time:", datetime.now())
print("================================")

# Load known devices
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        known_devices = json.load(f)
else:
    known_devices = {}

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

    for lease in leases:
        mac = lease.get('mac-address')
        # Address can be under 'address' or 'active-address'
        ip = lease.get('active-address', lease.get('address', 'Unknown IP'))
        hostname = lease.get('host-name', 'Unknown Device')
        status = lease.get('status', 'bound')
        
        # Only check bounded devices (or static ones if bounded isn't reported accurately by some RouterOS versions)
        if mac and mac not in known_devices:
            known_devices[mac] = {
                "first_seen": str(datetime.now()),
                "hostname": hostname,
                "ip": ip
            }
            new_devices.append((mac, hostname, ip))

    connection.disconnect()

    if new_devices:
        alert_msg = "📱 *NEW DEVICE DETECTED*\n\n"
        alert_msg += "The following new devices have connected to the network:\n"
        for mac, hostname, ip in new_devices:
            alert_msg += f"- Host: {hostname}\n  IP: {ip}\n  MAC: {mac}\n\n"
        
        print(f"Detected {len(new_devices)} new devices. Sending WhatsApp Alert...")
        subprocess.run([
            "python3",
            "alert.py",
            alert_msg
        ])
    else:
        print("No new devices detected.")

    # Save state
    with open(STATE_FILE, "w") as f:
        json.dump(known_devices, f, indent=4)
        
    print("Device tracking completed.")

except Exception as e:
    print("Error:", e)
