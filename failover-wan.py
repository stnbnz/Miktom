import routeros_api
import subprocess
import sys
import os
import django
import time
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import Router, FailoverState, FailoverEvent, ActivityLog
from alert import send_telegram

# ======================
# ROUTER CONFIG
# ======================

# Get active router from database
router = Router.objects.filter(is_active=True).first()
if not router:
    print("Error: No active router in database.")
    sys.exit(1)

ROUTER_IP = router.ip_address
USERNAME = router.username
PASSWORD = router.password

# ======================
# FAILOVER CONFIG
# ======================

PING_TARGET_1 = "8.8.8.8"
PING_TARGET_2 = "1.1.1.1"

ISP1_ROUTE_COMMENT = "ISP1_MAIN"
ISP2_ROUTE_COMMENT = "ISP2_BACKUP"

print("================================")
print(" MikroTik WAN Failover Guardian")
print(" Time:", datetime.now())
print(f" Router: {router.name} ({ROUTER_IP})")
print("================================")

# Get or create failover state
failover_state, _ = FailoverState.objects.get_or_create(
    router=router,
    defaults={'active_wan': 'ISP1_ACTIVE'}
)

def check_internet():
    """Check internet connectivity via ping"""
    try:
        p1 = subprocess.run(["ping", "-c", "2", "-W", "2", PING_TARGET_1], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p2 = subprocess.run(["ping", "-c", "2", "-W", "2", PING_TARGET_2], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p1.returncode == 0 or p2.returncode == 0
    except Exception as e:
        print(f"Ping check error: {e}")
        return False

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
        print(f"Warning: Cannot find routes with comments '{ISP1_ROUTE_COMMENT}' and '{ISP2_ROUTE_COMMENT}'")
    else:
        internet_up = check_internet()
        previous_wan = failover_state.active_wan
        
        if failover_state.active_wan == "ISP1_ACTIVE":
            if not internet_up:
                print("ISP1 appears to be DOWN. Failing over to ISP2...")
                routes_api.set(id=isp1_route['.id'], distance="3")
                failover_state.active_wan = "ISP2_ACTIVE"
                failover_state.save()
                
                # Log failover event
                FailoverEvent.objects.create(
                    router=router,
                    previous_wan='ISP1_ACTIVE',
                    new_wan='ISP2_ACTIVE',
                    event_type='failover',
                    detail='ISP1 connectivity lost, switched to ISP2'
                )
                
                alert_msg = "🔄 *WAN FAILOVER TRIGGERED*\n\nISP 1 (Main) is DOWN! 🔴\nTraffic shifted to ISP 2 (Backup) 🟢"
                send_telegram(alert_msg)
                
                ActivityLog.objects.create(
                    router=router,
                    activity_type='failover',
                    description='WAN failover triggered: ISP1 to ISP2',
                    success=True
                )
            else:
                print("ISP1 is UP and active. No action needed.")
                
        elif failover_state.active_wan == "ISP2_ACTIVE":
            if internet_up:
                print("Attempting to restore ISP1 as main WAN...")
                routes_api.set(id=isp1_route['.id'], distance="1")
                
                time.sleep(5)
                
                if check_internet():
                    print("ISP1 restoration successful.")
                    failover_state.active_wan = "ISP1_ACTIVE"
                    failover_state.save()
                    
                    # Log restore event
                    FailoverEvent.objects.create(
                        router=router,
                        previous_wan='ISP2_ACTIVE',
                        new_wan='ISP1_ACTIVE',
                        event_type='restore',
                        detail='ISP1 connectivity restored'
                    )
                    
                    alert_msg = "✅ *PRIMARY WAN RESTORED*\n\nISP 1 (Main) is back ONLINE! 🟢\nTraffic shifted back to primary link."
                    send_telegram(alert_msg)
                    
                    ActivityLog.objects.create(
                        router=router,
                        activity_type='failover',
                        description='WAN failover restored: ISP2 to ISP1',
                        success=True
                    )
                else:
                    print("ISP1 still down. Keeping ISP2 active.")
                    routes_api.set(id=isp1_route['.id'], distance="3")
            else:
                print("Both ISP links appear to be down. Total outage.")
                
                ActivityLog.objects.create(
                    router=router,
                    activity_type='failover',
                    description='Complete WAN outage detected',
                    success=False
                )

    connection.disconnect()
    print("Failover check completed successfully")

except Exception as e:
    print(f"Error: {e}")
    ActivityLog.objects.create(
        router=router,
        activity_type='failover',
        description='Failover check failed',
        metadata={'error': str(e)},
        success=False,
        error_message=str(e)
    )
