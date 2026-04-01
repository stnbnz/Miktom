  import routeros_api
import json
import os
from datetime import datetime
from alert import send_telegram

# ======================
# ROUTER CONFIG
# ======================
ROUTER_IP = "192.168.1.2"
USERNAME = "admin"
PASSWORD = ""

STATE_FILE = "/home/stnbnz/miktom/router_state.json"

CPU_THRESHOLD = 80
RAM_THRESHOLD = 80
FLAP_THRESHOLD = 3

# ======================
# LOAD OLD STATE
# ======================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        old_state = json.load(f)
else:
    old_state = {}

new_state = {}
alerts = []

print("================================")
print(" MikroTik Advanced Monitoring")
print(" Time:", datetime.now())
print("================================")

# ======================
# CONNECT TO MIKROTIK
# ======================
connection = routeros_api.RouterOsApiPool(
    ROUTER_IP,
    username=USERNAME,
    password=PASSWORD,
    port=8728,
    plaintext_login=True
)

api = connection.get_api()

# ======================
# INTERFACE MONITORING
# ======================
interface_api = api.get_resource('/interface')
interfaces = interface_api.get()

for iface in interfaces:
    if iface.get("type") != "ether":
        continue

    name = iface["name"]
    running = iface["running"]
    status = "UP" if running == "true" else "DOWN"

    new_state[name] = status
    old_status = old_state.get(name)

    if old_status is None:
        continue

    if old_status != status:
        flap_key = f"{name}_flap"
        flap_count = old_state.get(flap_key, 0) + 1
        new_state[flap_key] = flap_count

        if flap_count >= FLAP_THRESHOLD:
            alerts.append(f"⚠️ INTERFACE FLAPPING: {name}")
        else:
            if status == "DOWN":
                alerts.append(f"⚠️ Interface DOWN: {name}")
            else:
                alerts.append(f"✅ Interface RECOVERED: {name}")
    else:
        new_state[f"{name}_flap"] = 0

# ======================
# SYSTEM RESOURCE CHECK
# ======================
resource = api.get_resource('/system/resource').get()[0]

cpu_load = int(resource["cpu-load"])
total_mem = int(resource["total-memory"])
free_mem = int(resource["free-memory"])

ram_usage = int((1 - (free_mem / total_mem)) * 100)

if cpu_load > CPU_THRESHOLD:
    alerts.append(f"🔥 CPU HIGH: {cpu_load}%")

if ram_usage > RAM_THRESHOLD:
    alerts.append(f"🔥 RAM HIGH: {ram_usage}%")

# ======================
# INTERNET CHECK
# ======================
ping_api = api.get_binary_resource('/ping')

try:
    ping_result = ping_api.call("ping", {
        "address": "8.8.8.8",
        "count": "2"
    })
    internet_status = "UP" if ping_result else "DOWN"
except:
    internet_status = "DOWN"

old_internet = old_state.get("internet")
new_state["internet"] = internet_status

if old_internet and old_internet != internet_status:
    if internet_status == "DOWN":
        alerts.append("🌐 INTERNET DOWN")
    else:
        alerts.append("🌐 INTERNET RECOVERED")

connection.disconnect()

# ======================
# SEND ALERT
# ======================
if alerts:
    message = "\n".join(alerts)
    print("\n========== ALERT ==========")
    print(message)

    send_telegram(message)

else:
    print("\nNo incident detected")

# ======================
# SAVE STATE
# ======================
with open(STATE_FILE, "w") as f:
    json.dump(new_state, f, indent=4)

print("\nState saved")
print("Monitoring finished")
