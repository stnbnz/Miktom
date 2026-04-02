import routeros_api
import subprocess
import os
import sys
import mysql.connector

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from alert import send_telegram
except ImportError:
    def send_telegram(msg): pass

# State tracker
last_internet_status = "UP"
last_interface_status = {}
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
    global last_internet_status
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
        ping_latency = "0"
        try:
            ping_result = api.get_resource('/').call("ping", {
                "address": "8.8.8.8",
                "count": "1"
            })
            if ping_result and int(ping_result[0].get("received", 0)) > 0:
                internet_status = "UP"
                time_val = ping_result[0].get("time", "0ms")
                if "ms" in time_val:
                    ping_latency = time_val.split("ms")[0]
                else:
                    ping_latency = "0"
        except Exception:
            internet_status = "DOWN"

        # Additional System Metrics (Users & Security)
        active_users = 0
        try:
            hotspot_users = len(api.get_resource('/ip/hotspot/active').get())
            ppp_users = len(api.get_resource('/ppp/active').get())
            active_users = hotspot_users + ppp_users
        except Exception: pass

        banned_ips = 0
        try:
            banned_ips = len(api.get_resource('/ip/firewall/address-list').get(**{'list': 'AUTO-BANNED'}))
        except Exception: pass

        # Check overall state changes and aggregate alerts
        import threading
        messages_to_send = []

        if internet_status == "DOWN" and last_internet_status == "UP":
            messages_to_send.append("⚠️ INTERNET CONNECTION IS DOWN!")
        elif internet_status == "UP" and last_internet_status == "DOWN":
            messages_to_send.append("✅ INTERNET CONNECTION RECOVERED!")
        
        last_internet_status = internet_status

        for iface in interfaces_data:
            name = iface["name"]
            status = iface["status"]
            
            old_status = last_interface_status.get(name, "UP") # assume UP initially
            if status == "DOWN" and old_status == "UP":
                messages_to_send.append(f"⚠️ Interface {name} is DOWN!")
            elif status == "UP" and old_status == "DOWN":
                messages_to_send.append(f"✅ Interface {name} RECOVERED!")
            
            last_interface_status[name] = status

        if messages_to_send:
            combined_message = "🔔 STATE CHANGE DETECTED:\n" + "\n".join(messages_to_send)
            threading.Thread(target=send_telegram, args=(combined_message,)).start()

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
            "ping_latency": ping_latency,
            "active_users": active_users,
            "banned_ips": banned_ips,
            "interfaces": interfaces_data,
            "alerts": alerts
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })

import io
import zipfile
from django.http import HttpResponse

def trigger_backup(request):
    """API endpoint to run backup.py and serve ZIP download"""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backup.py")
        python_exe = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "venv", "Scripts", "python.exe")
        
        # Block until backup.py finishes
        subprocess.run([python_exe, script_path], cwd=os.path.dirname(script_path), capture_output=True)
        
        db = mysql.connector.connect(host="127.0.0.1", user="root", password="", database="mikrotik_automation")
        cursor = db.cursor()
        cursor.execute("SELECT backup_file, backup_time FROM backup_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        db.close()
        
        if not row:
            return JsonResponse({"success": False, "error": "No backup log found."})
            
        backup_file = row[0]
        date_folder = row[1].strftime("%Y-%m-%d")
        
        # Locate files on disk (Absolute mapping relative to drive root)
        base_dir = os.path.abspath(f"/home/stnbnz/miktom/mikrotik-backup/192.168.1.2/{date_folder}")
        
        bpath = os.path.join(base_dir, backup_file)
        export_file = backup_file.replace("backup_", "export_").replace(".backup", ".rsc")
        epath = os.path.join(base_dir, export_file)
        
        if not os.path.isfile(bpath) and not os.path.isfile(epath):
            return JsonResponse({"success": False, "error": f"Backup script ran, but files not found in {base_dir}"})
            
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isfile(bpath): zipf.write(bpath, arcname=backup_file)
            if os.path.isfile(epath): zipf.write(epath, arcname=export_file)
            
        buffer.seek(0)
        
        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="Mikrotik_ManualBackup_{row[1].strftime("%Y%m%d_%H%M")}.zip"'
        return response
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })

def backup_history(request):
    """API endpoint to get last 5 mysql backup logs"""
    try:
        db = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="",
            database="mikrotik_automation"
        )
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT backup_time, backup_file, status FROM backup_log ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        db.close()
        
        for row in rows:
            if isinstance(row['backup_time'], datetime):
                row['backup_time'] = row['backup_time'].strftime("%Y-%m-%d %H:%M")
                
        return JsonResponse({"success": True, "data": rows})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def reboot_router(request):
    """API endpoint to reboot router remote"""
    if request.method == "POST":
        try:
            connection = routeros_api.RouterOsApiPool(
                ROUTER_IP, username=USERNAME, password=PASSWORD, port=8728, plaintext_login=True
            )
            api = connection.get_api()
            try:
                # System will disconnect connection upon reboot
                api.get_resource('/system').call('reboot')
            except Exception:
                pass
            
            # The code continues without crashing since disconnection throws an internal socket exception handled by our pass
            return JsonResponse({"success": True, "message": "Router is rebooting, please wait..."})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request method."})

@csrf_exempt
def reset_router(request):
    """API endpoint to backup first, then reset router to factory defaults"""
    if request.method == "POST":
        try:
            # 1. TRIGGER BACKUP FIRST
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backup.py")
            python_exe = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "venv", "Scripts", "python.exe")
            
            subprocess.run([python_exe, script_path], cwd=os.path.dirname(script_path), capture_output=True)
            
            db = mysql.connector.connect(host="127.0.0.1", user="root", password="", database="mikrotik_automation")
            cursor = db.cursor()
            cursor.execute("SELECT backup_file, backup_time FROM backup_log ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            db.close()
            
            if not row:
                return JsonResponse({"success": False, "error": "Pre-reset Backup failed without logs."})
                
            backup_file = row[0]
            date_folder = row[1].strftime("%Y-%m-%d")
            base_dir = os.path.abspath(f"/home/stnbnz/miktom/mikrotik-backup/192.168.1.2/{date_folder}")
            
            bpath = os.path.join(base_dir, backup_file)
            export_file = backup_file.replace("backup_", "export_").replace(".backup", ".rsc")
            epath = os.path.join(base_dir, export_file)
            
            if not os.path.isfile(bpath) and not os.path.isfile(epath):
                return JsonResponse({"success": False, "error": f"Rescue Backup failed to fetch into {base_dir}"})
                
            # 2. TRIGGER RESET
            connection = routeros_api.RouterOsApiPool(
                ROUTER_IP, username=USERNAME, password=PASSWORD, port=8728, plaintext_login=True
            )
            api = connection.get_api()
            try:
                # Disconnects upon reset
                api.get_resource('/system').call('reset-configuration', {'skip-backup': 'yes'})
            except Exception:
                pass
                
            # 3. ZIP BACKUP FILES AND RETURN
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.isfile(bpath): zipf.write(bpath, arcname=backup_file)
                if os.path.isfile(epath): zipf.write(epath, arcname=export_file)
                
            buffer.seek(0)
            
            response = HttpResponse(buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="Mikrotik_PreReset_Rescue_{row[1].strftime("%Y%m%d_%H%M")}.zip"'
            return response
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request method."})
