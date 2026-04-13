import routeros_api
import sys
import os
import django
import re
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from web_monitor.dashboard.models import Router, SecurityEvent, ActivityLog
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
# SECURITY CONFIG
# ======================

BAN_LIST_NAME = "AUTO-BANNED"
MAX_FAILURES = 5

print("================================")
print(" MikroTik Security Shield")
print(" Time:", datetime.now())
print(f" Router: {router.name} ({ROUTER_IP})")
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
    
    for log in logs:
        msg = log.get('message', '')
        if 'login failure' in msg:
            match = re.search(r'from (\d+\.\d+\.\d+\.\d+)', msg)
            if match:
                ip = match.group(1)
                failure_counts[ip] = failure_counts.get(ip, 0) + 1

    # 2. Get current banned IPs from database
    current_bans = SecurityEvent.objects.filter(
        router=router,
        action='banned'
    ).values_list('ip_address', flat=True).distinct()
    
    banned_ips = list(current_bans)
    new_bans = []

    # 3. Ban IPs exceeding threshold
    fw_address_list_api = api.get_resource('/ip/firewall/address-list')
    for ip, count in failure_counts.items():
        if count >= MAX_FAILURES and ip not in banned_ips:
            try:
                fw_address_list_api.add(
                    list=BAN_LIST_NAME,
                    address=ip,
                    comment=f"Auto-banned by Security Shield ({count} failed logins)",
                    timeout="1d"
                )
                print(f"[!] Banning IP: {ip} (Failed attempts: {count})")
                new_bans.append(ip)
                
                # Log security event
                SecurityEvent.objects.create(
                    router=router,
                    ip_address=ip,
                    failure_count=count,
                    action='banned',
                    ban_duration='1d'
                )
            except Exception as e:
                print(f"Failed to ban IP {ip}: {e}")

    # 4. Ensure Drop rule exists
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
        alert_msg = f"🛡️ *SECURITY SHIELD ACTIVATED*\n\nThe following {len(new_bans)} IPs have been banned for 1 day:\n"
        for ip in new_bans:
            alert_msg += f"🚫 {ip}\n"
        
        print("\nSending alert...")
        send_telegram(alert_msg)
        
        ActivityLog.objects.create(
            router=router,
            activity_type='security_ban',
            description=f'Security Shield: {len(new_bans)} IPs banned',
            metadata={'banned_ips': new_bans},
            success=True
        )
    else:
        print("No new brute-force attacks detected.")

    print("Security Shield completed successfully")

except Exception as e:
    print(f"Error: {e}")
    ActivityLog.objects.create(
        router=router,
        activity_type='security_ban',
        description='Security Shield check failed',
        metadata={'error': str(e)},
        success=False,
        error_message=str(e)
    )
