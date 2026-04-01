import routeros_api
import subprocess
import os
from django.shortcuts import render
from django.http import JsonResponse
from datetime import datetime

# Router config
ROUTER_IP = "192.168.1.2"
USERNAME = "admin"
PASSWORD = ""

def index(request):
    """Render main dashboard HTML"""
    return render(request, 'dashboard/index.html')

def router_status(request):
    """API endpoint to get router stats dynamically"""
    try:
        connection = routeros_api.RouterOsApiPool(
            ROUTER_IP,
            username=USERNAME,
            password=PASSWORD,
            port=8728,
            plaintext_login=True
        )
        api = connection.get_api()

        # Get system resources
        try:
            resource = api.get_resource('/system/resource').get()[0]
            cpu_load = int(resource.get("cpu-load", 0))
            total_mem = int(resource.get("total-memory", 1))
            free_mem = int(resource.get("free-memory", 0))
            ram_usage = int((1 - (free_mem / total_mem)) * 100)
            uptime = resource.get("uptime", "0s")
            version = resource.get("version", "Unknown")
            board = resource.get("board-name", "Unknown")
        except Exception as e:
            cpu_load, total_mem, free_mem, ram_usage, uptime, version, board = 0, 0, 0, 0, "Error", "Error", "Error"

        # Get interface stats
        interfaces_data = []
        try:
            interface_api = api.get_resource('/interface')
            interfaces = interface_api.get()
            for iface in interfaces:
                if iface.get("type", "") == "ether":
                    name = iface.get("name", "Unknown")
                    running = iface.get("running", "false")
                    status = "UP" if running == "true" else "DOWN"
                    tx_byte = int(iface.get("tx-byte", 0))
                    rx_byte = int(iface.get("rx-byte", 0))
                    
                    interfaces_data.append({
                        "name": name,
                        "status": status,
                        "tx_byte": tx_byte,
                        "rx_byte": rx_byte,
                    })
        except Exception as e:
            pass

        # Ping test
        internet_status = "DOWN"
        try:
            ping_api = api.get_binary_resource('/ping')
            ping_result = ping_api.call("ping", {
                "address": "8.8.8.8",
                "count": "1"
            })
            internet_status = "UP" if ping_result else "DOWN"
        except Exception:
            internet_status = "DOWN"

        # Build Notifications/Alerts
        connection.disconnect()
        alerts = []
        time_now = datetime.now().strftime("%H:%M:%S")
        if cpu_load > 80:
            alerts.append({"type": "danger", "message": f"🔥 CPU is critically HIGH at {cpu_load}%", "time": time_now})
        if ram_usage > 80:
            alerts.append({"type": "danger", "message": f"🔥 RAM usage is HIGH at {ram_usage}%", "time": time_now})
        if internet_status == "DOWN":
            alerts.append({"type": "danger", "message": "🌐 INTERNET CONNECTION DOWN", "time": time_now})
        for iface in interfaces_data:
            if iface["status"] == "DOWN":
                alerts.append({"type": "warning", "message": f"⚠️ Interface {iface['name']} is DOWN", "time": time_now})
            else:
                alerts.append({"type": "success", "message": f"✅ Interface {iface['name']} is UP", "time": time_now})
        
        if not alerts:
            alerts.append({"type": "success", "message": "✅ System is running smoothly", "time": time_now})

        return JsonResponse({
            "success": True,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_load": cpu_load,
            "ram_usage": ram_usage,
            "free_mem_mb": free_mem // (1024 * 1024),
            "total_mem_mb": total_mem // (1024 * 1024),
            "uptime": uptime,
            "version": version,
            "board": board,
            "internet_status": internet_status,
            "interfaces": interfaces_data,
            "alerts": alerts
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })

def trigger_backup(request):
    """API endpoint to trigger backup.py"""
    try:
        # Path to backup script relative to web_monitor/manage.py
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backup.py")
        
        # We run the command asynchronously or capture output if possible.
        # It's better to run it via Popen and not block forever, but let's just trigger it.
        # The script backup.py relies on some external libs (paramiko, mysql-connector).
        # We assume they are installed in the venv.
        python_exe = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "venv", "Scripts", "python.exe")
        
        # Fire and forget
        subprocess.Popen([python_exe, script_path], cwd=os.path.dirname(script_path))
        
        return JsonResponse({
            "success": True,
            "message": "Backup triggered successfully in the background."
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })
