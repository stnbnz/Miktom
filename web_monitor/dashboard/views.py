import routeros_api
import subprocess
import os
import sys
import random
import string
import uuid
import mysql.connector
from datetime import datetime, timedelta


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

from .models import Voucher, Router

def _get_active_router(request):
    router_id = request.session.get('active_router_id')
    if router_id:
        try:
            return Router.objects.get(id=router_id)
        except Router.DoesNotExist:
            pass
    router = Router.objects.first()
    if router:
        request.session['active_router_id'] = router.id
    return router

def _get_mikrotik_api_for_router(router):
    if not router:
        raise Exception("No router configured")
    conn = routeros_api.RouterOsApiPool(
        router.ip_address, username=router.username, password=router.password,
        port=router.port, plaintext_login=True
    )
    return conn, conn.get_api()

def index(request):
    """Render main dashboard HTML"""
    return render(request, 'dashboard/index.html')

def router_status(request):
    global last_internet_status
    """API endpoint to get router stats dynamically"""
    try:
        router = _get_active_router(request)
        if not router:
            return JsonResponse({"success": False, "error": "No router configured. Please add one in Settings."})
        connection, api = _get_mikrotik_api_for_router(router)

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
        router = _get_active_router(request)
        if not router:
            return JsonResponse({"success": False, "error": "No router configured."})
            
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backup.py")
        python_exe = sys.executable
        
        # Block until backup.py finishes
        subprocess.run([python_exe, script_path, router.ip_address, router.username, router.password], cwd=os.path.dirname(script_path), capture_output=True)
        
        db = mysql.connector.connect(host="127.0.0.1", user="root", password="", database="mikrotik_automation")
        cursor = db.cursor()
        cursor.execute("SELECT backup_file, backup_time FROM backup_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        db.close()
        
        if not row:
            return JsonResponse({"success": False, "error": "No backup log found."})
            
        backup_file = row[0]
        date_folder = row[1].strftime("%Y-%m-%d")
        
        # Locate files on disk (path relative to project root)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "mikrotik-backup", router.ip_address, date_folder))
        
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
            router = _get_active_router(request)
            if not router: return JsonResponse({"success": False, "error": "No router configured."})
            connection, api = _get_mikrotik_api_for_router(router)
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
            router = _get_active_router(request)
            if not router: return JsonResponse({"success": False, "error": "No router configured."})
            
            # 1. TRIGGER BACKUP FIRST
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backup.py")
            python_exe = sys.executable
            
            subprocess.run([python_exe, script_path, router.ip_address, router.username, router.password], cwd=os.path.dirname(script_path), capture_output=True)
            
            db = mysql.connector.connect(host="127.0.0.1", user="root", password="", database="mikrotik_automation")
            cursor = db.cursor()
            cursor.execute("SELECT backup_file, backup_time FROM backup_log ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            db.close()
            
            if not row:
                return JsonResponse({"success": False, "error": "Pre-reset Backup failed without logs."})
                
            backup_file = row[0]
            date_folder = row[1].strftime("%Y-%m-%d")
            base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "mikrotik-backup", router.ip_address, date_folder))
            
            bpath = os.path.join(base_dir, backup_file)
            export_file = backup_file.replace("backup_", "export_").replace(".backup", ".rsc")
            epath = os.path.join(base_dir, export_file)
            
            if not os.path.isfile(bpath) and not os.path.isfile(epath):
                return JsonResponse({"success": False, "error": f"Rescue Backup failed to fetch into {base_dir}"})
                
            # 2. TRIGGER RESET
            connection, api = _get_mikrotik_api_for_router(router)
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

# =================================================
# VOUCHER BILLING VIEWS
# =================================================
from .models import Voucher
import json as json_lib

PROFILE_DURATION = {
    '1jam':    {'hours': 1,    'label': '1 Jam',    'price': 3000},
    '3jam':    {'hours': 3,    'label': '3 Jam',    'price': 5000},
    '1hari':   {'hours': 24,   'label': '1 Hari',   'price': 10000},
    '1minggu': {'hours': 168,  'label': '1 Minggu', 'price': 50000},
}

def _gen_code():
    """Generate kode voucher unik format XXXX-XXXXX"""
    prefix = ''.join(random.choices(string.ascii_uppercase, k=4))
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}-{suffix}"

def _get_mikrotik_api(router):
    return _get_mikrotik_api_for_router(router)

def voucher_page(request):
    """Render halaman manajemen voucher"""
    return render(request, 'dashboard/voucher.html', {
        'profiles': PROFILE_DURATION
    })

@csrf_exempt
def generate_vouchers(request):
    """Generate batch voucher dan push ke MikroTik Hotspot User"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST only'})
    try:
        data = json_lib.loads(request.body)
        profile  = data.get('profile', '1jam')
        quantity = int(data.get('quantity', 1))
        custom_price = data.get('price', None)

        quantity = max(1, min(quantity, 100))  # Batasi 1-100
        if profile not in PROFILE_DURATION:
            return JsonResponse({'success': False, 'error': 'Profile tidak valid'})

        info      = PROFILE_DURATION[profile]
        hours     = info['hours']
        price     = int(custom_price) if custom_price is not None else info['price']
        batch_id  = uuid.uuid4().hex[:8].upper()

        router = _get_active_router(request)
        conn, api = _get_mikrotik_api_for_router(router)
        hotspot_user = api.get_resource('/ip/hotspot/user')

        created_codes = []
        for _ in range(quantity):
            code = _gen_code()
            while Voucher.objects.filter(code=code).exists():
                code = _gen_code()

            # Push ke MikroTik sebagai Hotspot User
            hotspot_user.add(**{
                'name':    code,
                'password': code,
                'profile': 'default',
                'comment': f'Voucher {info["label"]} - Batch {batch_id}',
                'limit-uptime': f'{hours}h',
            })

            Voucher.objects.create(
                code=code,
                profile=profile,
                duration_hours=hours,
                price=price,
                batch=batch_id,
            )
            created_codes.append(code)

        conn.disconnect()
        return JsonResponse({
            'success': True,
            'batch': batch_id,
            'codes': created_codes,
            'count': len(created_codes),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def get_vouchers(request):
    """List semua voucher dari DB, sertakan status dari MikroTik"""
    try:
        # Cek active sessions di MikroTik
        active_codes = set()
        try:
            router = _get_active_router(request)
            conn, api = _get_mikrotik_api_for_router(router)
            active_sessions = api.get_resource('/ip/hotspot/active').get()
            for s in active_sessions:
                active_codes.add(s.get('user', ''))
            conn.disconnect()
        except Exception:
            pass

        vouchers = Voucher.objects.all()[:200]
        data = []
        for v in vouchers:
            online = v.code in active_codes
            data.append({
                'id':             v.id,
                'code':           v.code,
                'profile':        v.profile,
                'profile_label':  PROFILE_DURATION.get(v.profile, {}).get('label', v.profile),
                'duration_hours': v.duration_hours,
                'price':          v.price,
                'is_used':        v.is_used,
                'online':         online,
                'batch':          v.batch,
                'created_at':     v.created_at.strftime('%Y-%m-%d %H:%M'),
                'used_at':        v.used_at.strftime('%Y-%m-%d %H:%M') if v.used_at else None,
            })
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def delete_voucher(request, code):
    """Hapus voucher dari MikroTik dan DB"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST only'})
    try:
        # Hapus dari MikroTik
        try:
            router = _get_active_router(request)
            conn, api = _get_mikrotik_api_for_router(router)
            hotspot_user = api.get_resource('/ip/hotspot/user')
            users = hotspot_user.get(**{'name': code})
            if users:
                hotspot_user.remove(id=users[0]['.id'])
            conn.disconnect()
        except Exception:
            pass

        # Hapus dari DB
        Voucher.objects.filter(code=code).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def print_vouchers(request):
    """Render print-friendly voucher cards"""
    codes = request.GET.get('codes', '').split(',')
    codes = [c.strip() for c in codes if c.strip()]

    if not codes:
        # Print semua yang belum dipakai
        vouchers = Voucher.objects.filter(is_used=False)
    else:
        vouchers = Voucher.objects.filter(code__in=codes)

    profiles = PROFILE_DURATION
    return render(request, 'dashboard/voucher_print.html', {
        'vouchers': vouchers,
        'profiles': profiles,
        'print_time': datetime.now().strftime('%d %B %Y %H:%M'),
    })

def active_users(request):
    """Render active users page"""
    return render(request, 'dashboard/active_users.html')

def active_users_data(request):
    """API endpoint to get active users data from MikroTik"""
    try:
        router = _get_active_router(request)
        if not router:
            return JsonResponse({'success': False, 'error': 'No router configured'})
        
        conn, api = _get_mikrotik_api_for_router(router)
        active_list = []
        
        try:
            hotspot_active = api.get_resource('/ip/hotspot/active').get()
            for user in hotspot_active:
                active_list.append({
                    'id': user.get('.id'),
                    'server': user.get('server', ''),
                    'user': user.get('user', ''),
                    'address': user.get('address', ''),
                    'mac_address': user.get('mac-address', ''),
                    'uptime': user.get('uptime', ''),
                    'bytes_in': int(user.get('bytes-in', 0)),
                    'bytes_out': int(user.get('bytes-out', 0)),
                    'type': 'Hotspot'
                })
        except Exception:
            pass
            
        conn.disconnect()
        return JsonResponse({'success': True, 'data': active_list})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def kick_hotspot_user(request):
    """API endpoint to kick active hotspot user"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST only'})
    try:
        data = json_lib.loads(request.body)
        user_id = data.get('id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'No ID provided'})
            
        router = _get_active_router(request)
        if not router:
            return JsonResponse({'success': False, 'error': 'No router configured'})
            
        conn, api = _get_mikrotik_api_for_router(router)
        try:
            api.get_resource('/ip/hotspot/active').remove(id=user_id)
        except Exception as e:
            pass
            
        conn.disconnect()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def settings_page(request):
    """Render settings page"""
    return render(request, 'dashboard/settings.html')

def get_routers(request):
    routers = Router.objects.all()
    active_id = request.session.get('active_router_id')
    
    if not active_id and routers.exists():
        active_id = routers.first().id
        request.session['active_router_id'] = active_id
        
    data = [{
        'id': r.id,
        'name': r.name,
        'ip_address': r.ip_address,
        'username': r.username,
        'port': r.port
    } for r in routers]
    
    return JsonResponse({'success': True, 'data': data, 'active_id': active_id})

@csrf_exempt
def add_router(request):
    if request.method == 'POST':
        try:
            data = json_lib.loads(request.body)
            r = Router.objects.create(
                name=data.get('name'),
                ip_address=data.get('ip_address'),
                username=data.get('username'),
                password=data.get('password', ''),
                port=int(data.get('port', 8728))
            )
            if Router.objects.count() == 1:
                request.session['active_router_id'] = r.id
            return JsonResponse({'success': True, 'id': r.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def delete_router(request, id):
    if request.method == 'POST':
        Router.objects.filter(id=id).delete()
        if request.session.get('active_router_id') == id:
            del request.session['active_router_id']
        return JsonResponse({'success': True})

@csrf_exempt
def set_active_router(request):
    if request.method == 'POST':
        data = json_lib.loads(request.body)
        router_id = data.get('id')
        if Router.objects.filter(id=router_id).exists():
            request.session['active_router_id'] = router_id
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Router not found'})
