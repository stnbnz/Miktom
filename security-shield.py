import routeros_api
import subprocess
import os
import re
from datetime import datetime

# ======================
# ROUTER CONFIG
# ======================

ROUTER_IP = "192.168.88.1"
USERNAME = "admin"
PASSWORD = "1945"

# ======================
# SECURITY CONFIG
# ======================

BAN_LIST_NAME = "AUTO-BANNED"
MAX_FAILURES = 5

print("================================")
print(" MikroTik Security Shield")
print(" Time:", datetime.now())
print("================================")

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()

    # 1. Fetch system logs to find login failures
    log_api = api.get_resource('/log')
    logs = log_api.get()

    failure_counts = {}
    
    # We look for typical MikroTik login failure messages:
    # "login failure for user admin from 192.168.88.254 via ssh"
    for log in logs:
        msg = log.get('message', '')
        if 'login failure' in msg:
            # Extract IP using regex
            match = re.search(r'from (\d+\.\d+\.\d+\.\d+)', msg)
            if match:
                ip = match.group(1)
                failure_counts[ip] = failure_counts.get(ip, 0) + 1

    # 2. Get current banned IPs to avoid duplicate bans
    fw_address_list_api = api.get_resource('/ip/firewall/address-list')
    current_bans = fw_address_list_api.get(list=BAN_LIST_NAME)
    
    banned_ips = [b['address'] for b in current_bans]
    
    new_bans = []

    # 3. Ban IPs exceeding threshold
    for ip, count in failure_counts.items():
        if count >= MAX_FAILURES and ip not in banned_ips:
            try:
                fw_address_list_api.add(
                    list=BAN_LIST_NAME,
                    address=ip,
                    comment=f"Auto-banned by Security Shield ({count} failed logins)",
                    timeout="1d" # Ban for 1 day
                )
                print(f"[!] Banning IP: {ip} (Failed attempts: {count})")
                new_bans.append(ip)
            except Exception as e:
                print(f"Failed to ban IP {ip}: {e}")

    # 4. Ensure we have a Drop rule for our Address List
    fw_filter_api = api.get_resource('/ip/firewall/filter')
    filters = fw_filter_api.get()
    
    rule_exists = any(
        f.get('action') == 'drop' and f.get('src-address-list') == BAN_LIST_NAME
        for f in filters
    )
    
    if not rule_exists:
        print("[+] Creating Drop rule for AUTO-BANNED list")
        fw_filter_api.add(
            chain='input',
            action='drop',
            **{'src-address-list': BAN_LIST_NAME},
            comment="Security Shield: Drop Auto-banned IPs"
        )

    connection.disconnect()

    # 5. Send Alert if new IPs were banned
    if new_bans:
        alert_msg = "🛡️ *SECURITY SHIELD ACTIVATED*\n\n"
        alert_msg += "The following IPs have been automatically BANNED for 1 day due to multiple login failures:\n"
        for ip in new_bans:
            alert_msg += f"🚫 {ip}\n"
        
        print("\nSending WhatsApp Alert...")
        subprocess.run([
            "python3",
            "alert.py",
            alert_msg
        ])
    else:
        print("No new brute-force attacks detected.")

except Exception as e:
    print("Error:", e)

print("Security Shield completed.")
