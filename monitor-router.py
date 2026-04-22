import routeros_api
import sys
import os
import django
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import Router, SystemMetrics, ActivityLog, MonitorState, ActiveUser, InterfaceMetrics
try:
    from alert import send_telegram_markdown, send_telegram
except ImportError:
    def send_telegram_markdown(msg): print("[alert] Not available:", msg)
    def send_telegram(msg): print("[alert] Not available:", msg)

# ======================
# ROUTER CONFIG
# ======================

if len(sys.argv) >= 4:
    ROUTER_IP = sys.argv[1]
    USERNAME = sys.argv[2]
    PASSWORD = sys.argv[3]
    router, _ = Router.objects.get_or_create(
        ip_address=ROUTER_IP,
        defaults={'name': ROUTER_IP, 'username': USERNAME, 'password': PASSWORD}
    )
else:
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

print("================================")
print(" MikroTik Advanced Monitoring")
print(f" Time: {datetime.now()}")
print(f" Router: {router.name} ({ROUTER_IP})")
print("================================")

# Load previous state from MonitorState (JSON in DB)
monitor_state, _ = MonitorState.objects.get_or_create(
    router=router,
    defaults={'state_data': {}}
)
old_state = monitor_state.state_data  # dict: {iface_name: 'UP'/'DOWN', 'ether1_flap': 0, 'internet': 'UP'}

new_state = {}
alerts = []

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=router.port,
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
        running = iface.get("running", "false")
        status = "UP" if running == "true" else "DOWN"
        new_state[name] = status

        old_status = old_state.get(name)

        if old_status and old_status != status:
            flap_key = f"{name}_flap"
            flap_count = old_state.get(flap_key, 0) + 1
            new_state[flap_key] = flap_count

            if flap_count >= FLAP_THRESHOLD:
                alerts.append(f"⚠️ INTERFACE FLAPPING: `{name}` (flapped {flap_count}x)")
            else:
                if status == "DOWN":
                    alerts.append(f"🔴 Interface DOWN: `{name}`")
                else:
                    alerts.append(f"✅ Interface RECOVERED: `{name}`")
        else:
            new_state[f"{name}_flap"] = old_state.get(f"{name}_flap", 0)

        print(f"  Interface {name}: {status}")

    # ======================
    # SYSTEM RESOURCE CHECK
    # ======================
    resource_api = api.get_resource('/system/resource')
    resource = resource_api.get()[0]

    cpu_load = int(resource.get("cpu-load", 0))
    total_mem = int(resource.get("total-memory", 1))
    free_mem = int(resource.get("free-memory", 0))
    ram_usage = int((1 - (free_mem / total_mem)) * 100) if total_mem > 0 else 0
    uptime = resource.get("uptime", "0s")
    version = resource.get("version", "Unknown")
    board_name = resource.get("board-name", "Unknown")

    print(f"  CPU: {cpu_load}% | RAM: {ram_usage}%")

    if cpu_load > CPU_THRESHOLD:
        alerts.append(f"🔥 CPU HIGH: `{cpu_load}%` (threshold: {CPU_THRESHOLD}%)")

    if ram_usage > RAM_THRESHOLD:
        alerts.append(f"🔥 RAM HIGH: `{ram_usage}%` (threshold: {RAM_THRESHOLD}%)")

    # ======================
    # INTERNET CHECK
    # ======================
    internet_status = "DOWN"
    ping_latency = 0
    try:
        ping_result = api.get_resource('/').call("ping", {
            "address": "8.8.8.8",
            "count": "2"
        })
        if ping_result and int(ping_result[0].get("received", 0)) > 0:
            internet_status = "UP"
            time_val = ping_result[0].get("time", "0ms")
            if "ms" in time_val:
                try:
                    ping_latency = int(time_val.split("ms")[0])
                except ValueError:
                    ping_latency = 0
    except Exception as ping_err:
        print(f"  Ping check error: {ping_err}")
        internet_status = "DOWN"

    print(f"  Internet: {internet_status} | Ping: {ping_latency}ms")
    new_state["internet"] = internet_status

    old_internet = old_state.get("internet")
    if old_internet and old_internet != internet_status:
        if internet_status == "DOWN":
            alerts.append("🌐 *INTERNET CONNECTION LOST!*")
        else:
            alerts.append("✅ *INTERNET CONNECTION RESTORED!*")

    # Active users
    active_users_count = 0
    active_users_list = []
    try:
        hotspot_users = api.get_resource('/ip/hotspot/active').get()
        for u in hotspot_users:
            active_users_list.append({
                'user_id': u.get('.id', ''),
                'username': u.get('user', ''),
                'ip_address': u.get('address', ''),
                'mac_address': u.get('mac-address', ''),
                'server': u.get('server', ''),
                'uptime': u.get('uptime', ''),
                'bytes_in': int(u.get('bytes-in', 0)),
                'bytes_out': int(u.get('bytes-out', 0)),
                'session_type': 'hotspot'
            })
        active_users_count += len(hotspot_users)
        
        ppp_users = api.get_resource('/ppp/active').get()
        for u in ppp_users:
            active_users_list.append({
                'user_id': u.get('.id', ''),
                'username': u.get('name', ''),
                'ip_address': u.get('address', ''),
                'mac_address': u.get('caller-id', ''),
                'server': u.get('service', 'pppoe'),
                'uptime': u.get('uptime', ''),
                'bytes_in': 0, # Interface based usually
                'bytes_out': 0,
                'session_type': 'pppoe'
            })
        active_users_count += len(ppp_users)
    except Exception:
        pass

    banned_ips = 0
    try:
        banned_ips = len(api.get_resource('/ip/firewall/address-list').get(**{'list': 'AUTO-BANNED'}))
    except Exception:
        pass

    connection.disconnect()

    # ======================
    # SAVE METRICS
    # ======================
    sys_metric = SystemMetrics.objects.create(
        router=router,
        cpu_load=cpu_load,
        ram_usage=ram_usage,
        free_memory_mb=free_mem // (1024 * 1024),
        total_memory_mb=total_mem // (1024 * 1024),
        uptime=uptime,
        version=version,
        board_name=board_name,
        internet_status=internet_status,
        ping_latency=ping_latency,
        active_users=active_users_count,
        banned_ips=banned_ips
    )

    # Save Interface Metrics
    try:
        for iface in interfaces:
            if iface.get("type") == "ether":
                running = iface.get("running", "false")
                status = "UP" if running == "true" else "DOWN"
                InterfaceMetrics.objects.create(
                    router=router,
                    system_metric=sys_metric,
                    name=iface.get("name", "Unknown"),
                    status=status,
                    tx_bytes=int(iface.get("tx-byte", 0)),
                    rx_bytes=int(iface.get("rx-byte", 0))
                )
    except Exception as e:
        print(f"Error saving interfaces: {e}")

    # Synchronize ActiveUsers
    try:
        # Mark all current active as false to start fresh
        ActiveUser.objects.filter(router=router, is_active=True).update(is_active=False)
        for au in active_users_list:
            ActiveUser.objects.create(
                router=router,
                user_id=au['user_id'],
                username=au['username'],
                ip_address=au['ip_address'],
                mac_address=au['mac_address'],
                server=au['server'],
                uptime=au['uptime'],
                bytes_in=au['bytes_in'],
                bytes_out=au['bytes_out'],
                session_type=au['session_type'],
                is_active=True
            )
    except Exception as e:
        print(f"Error saving active users: {e}")

    # Update MonitorState for next run comparison
    monitor_state.state_data = new_state
    monitor_state.save()

    # ======================
    # SEND ALERT
    # ======================
    if alerts:
        alert_body = "\n".join(alerts)
        message = (
            f"🔔 *Monitoring Alert — {router.name}*\n\n"
            f"{alert_body}\n\n"
            f"CPU: `{cpu_load}%` | RAM: `{ram_usage}%` | Internet: `{internet_status}`"
        )
        print("\n========== ALERTS ==========")
        print("\n".join(alerts))
        send_telegram_markdown(message)

        ActivityLog.objects.create(
            router=router,
            activity_type='failover',
            description=f'Monitoring alerts: {len(alerts)} issues detected',
            metadata={'alerts': alerts},
            success=False
        )
    else:
        print("\n✅ All systems normal — no alerts.")

    print("Monitoring completed successfully.")

except Exception as e:
    print(f"\nError during monitoring: {e}")
    try:
        ActivityLog.objects.create(
            router=router,
            activity_type='failover',
            description='Router monitoring check failed',
            metadata={'error': str(e)},
            success=False,
            error_message=str(e)
        )
    except Exception as db_err:
        print(f"Also failed to log to DB: {db_err}")
