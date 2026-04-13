import routeros_api
import sys
import os
import django
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from web_monitor.dashboard.models import Router, SystemMetrics, ActivityLog
from alert import send_telegram

# ======================
# ROUTER CONFIG
# ======================

if len(sys.argv) >= 4:
    ROUTER_IP = sys.argv[1]
    USERNAME = sys.argv[2]
    PASSWORD = sys.argv[3]
    # Get or create router in database
    router, _ = Router.objects.get_or_create(
        ip_address=ROUTER_IP,
        defaults={'name': ROUTER_IP, 'username': USERNAME, 'password': PASSWORD}
    )
else:
    # Use active router from database
    router = Router.objects.filter(is_active=True).first()
    if not router:
        print("Error: No active router in database.")
        sys.exit(1)
    ROUTER_IP = router.ip_address
    USERNAME = router.username
    PASSWORD = router.password

CPU_THRESHOLD = 80
RAM_THRESHOLD = 80
FLAP_THRESHOLD = 3

new_state = {}
alerts = []

print("================================")
print(" MikroTik Advanced Monitoring")
print(" Time:", datetime.now())
print(f" Router: {router.name} ({ROUTER_IP})")
print("================================")

# ======================
# CONNECT TO MIKROTIK
# ======================

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()

    # Get last system metrics from database for comparison
    old_metrics = SystemMetrics.objects.filter(router=router).order_by('-timestamp').first()

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
        
        if old_metrics:
            old_status = old_metrics.metadata.get(f"{name}_status") if hasattr(old_metrics, 'metadata') else None

            if old_status and old_status != status:
                flap_key = f"{name}_flap"
                flap_count = old_metrics.metadata.get(flap_key, 0) + 1 if hasattr(old_metrics, 'metadata') else 1
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

    cpu_load = int(resource.get("cpu-load", 0))
    total_mem = int(resource.get("total-memory", 1))
    free_mem = int(resource.get("free-memory", 0))

    ram_usage = int((1 - (free_mem / total_mem)) * 100) if total_mem > 0 else 0

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

    new_state["internet"] = internet_status
    
    if old_metrics:
        old_internet = old_metrics.metadata.get("internet_status") if hasattr(old_metrics, 'metadata') else None
        if old_internet and old_internet != internet_status:
            if internet_status == "DOWN":
                alerts.append("🌐 INTERNET DOWN")
            else:
                alerts.append("🌐 INTERNET RECOVERED")

    connection.disconnect()

    # ======================
    # SAVE METRICS TO DATABASE
    # ======================
    metrics = SystemMetrics.objects.create(
        router=router,
        cpu_load=cpu_load,
        ram_usage=ram_usage,
        free_memory_mb=free_mem // 1024,
        total_memory_mb=total_mem // 1024,
        internet_status=internet_status,
        metadata=new_state
    )

    # ======================
    # SEND ALERT
    # ======================
    if alerts:
        message = "\n".join(alerts)
        print("\n========== ALERT ==========")
        print(message)

        send_telegram(message)
        
        # Log activity
        ActivityLog.objects.create(
            router=router,
            activity_type='system_alert',
            description='Router monitoring alert',
            metadata={'alerts': alerts},
            success=False
        )
    else:
        print("\nNo incident detected")

    print("Monitoring finished successfully")

except Exception as e:
    print(f"Error during monitoring: {e}")
    ActivityLog.objects.create(
        router=router,
        activity_type='system_alert',
        description='Router monitoring failed',
        metadata={'error': str(e)},
        success=False,
        error_message=str(e)
    )
