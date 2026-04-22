import routeros_api
import paramiko
import os
import time
import sys
import django
from datetime import datetime, timedelta

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import Router, BackupLog, ActivityLog

try:
    from alert import send_telegram_markdown
except ImportError:
    def send_telegram_markdown(msg): print("[alert] Not available:", msg)

# ==========================
# ROUTER CONFIG
# ==========================

# Supports both CLI args and active router from DB
if len(sys.argv) >= 4:
    ROUTER_IP = sys.argv[1]
    USERNAME = sys.argv[2]
    PASSWORD = sys.argv[3]
    router = Router.objects.filter(ip_address=ROUTER_IP).first()
    if not router:
        print(f"Warning: Router {ROUTER_IP} not in DB — backup will run without DB link")
else:
    router = Router.objects.filter(is_active=True).first()
    if not router:
        print("Error: No active router in database.")
        print("Usage: python backup.py <ROUTER_IP> <USERNAME> <PASSWORD>")
        sys.exit(1)
    ROUTER_IP = router.ip_address
    USERNAME = router.username
    PASSWORD = router.password

print("================================")
print(" MikroTik Backup System")
print(f" Time: {datetime.now()}")
print(f" Router: {ROUTER_IP}")
print("================================")

# ==========================
# BACKUP PATHS
# ==========================

BASE_BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mikrotik-backup"))

now = datetime.now()
date_folder = now.strftime("%Y-%m-%d")
timestamp = now.strftime("%Y%m%d_%H%M")

backup_name = f"backup_{timestamp}"
export_name = f"export_{timestamp}"

router_backup_file = backup_name + ".backup"
router_export_file = export_name + ".rsc"

local_dir = os.path.join(BASE_BACKUP_DIR, ROUTER_IP, date_folder)
os.makedirs(local_dir, exist_ok=True)

local_backup = os.path.join(local_dir, router_backup_file)
local_export = os.path.join(local_dir, router_export_file)

status = "FAILED"
error_message = ""
start_time = time.time()

try:
    # ==========================
    # 1. CREATE BINARY BACKUP VIA API
    # ==========================
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()
    backup = api.get_resource('/system/backup')
    backup.call('save', {'name': backup_name})
    connection.disconnect()
    print(f"[1] Binary backup '{backup_name}' created on router.")

    # ==========================
    # 2. EXPORT CONFIG VIA SSH
    # ==========================
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ROUTER_IP, username=USERNAME, password=PASSWORD, timeout=15)
    ssh.exec_command(f"/export file={export_name}")
    time.sleep(3)  # Give router time to write the file
    ssh.close()
    print(f"[2] Config export '{export_name}' created on router.")

    # Wait for router to finish writing files
    time.sleep(5)

    # ==========================
    # 3. DOWNLOAD VIA SFTP
    # ==========================
    transport = paramiko.Transport((ROUTER_IP, 22))
    transport.connect(username=USERNAME, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(transport)

    remote_files = sftp.listdir()

    if router_backup_file in remote_files:
        sftp.get(router_backup_file, local_backup)
        print(f"[3] Binary backup downloaded: {local_backup}")
    else:
        print(f"[!] Warning: {router_backup_file} not found on router.")

    if router_export_file in remote_files:
        sftp.get(router_export_file, local_export)
        print(f"[3] Export config downloaded: {local_export}")
    else:
        print(f"[!] Warning: {router_export_file} not found on router.")

    sftp.close()
    transport.close()

    if os.path.exists(local_backup) or os.path.exists(local_export):
        status = "SUCCESS"
    else:
        status = "FAILED"
        error_message = "Files not found after SFTP download"

except Exception as e:
    print(f"Backup error: {e}")
    error_message = str(e)
    status = "FAILED"

# ==========================
# 4. LOG TO DATABASE
# ==========================
duration = int(time.time() - start_time)
backup_size = os.path.getsize(local_backup) if os.path.exists(local_backup) else 0
export_size = os.path.getsize(local_export) if os.path.exists(local_export) else 0
total_size = backup_size + export_size

try:
    if router:
        BackupLog.objects.create(
            router=router,
            backup_file=router_backup_file,
            export_file=router_export_file,
            status=status,
            file_size=total_size,
            duration=duration
        )

        ActivityLog.objects.create(
            router=router,
            activity_type='backup_auto',
            description=f'Backup {status} — {router_backup_file}',
            metadata={
                'backup_file': router_backup_file,
                'export_file': router_export_file,
                'backup_size_bytes': backup_size,
                'export_size_bytes': export_size,
                'total_size_bytes': total_size,
                'duration_seconds': duration,
                'status': status
            },
            success=(status == 'SUCCESS'),
            error_message=error_message
        )

    print(f"[4] Database log saved. Status: {status} | Duration: {duration}s | Size: {total_size} bytes")

except Exception as db_err:
    print(f"[!] Failed to save to database: {db_err}")

# ==========================
# 5. TELEGRAM NOTIFICATION
# ==========================
size_kb = total_size / 1024
router_name = router.name if router else ROUTER_IP

if status == "SUCCESS":
    alert_msg = (
        f"✅ *Backup Berhasil*\n\n"
        f"Router: `{router_name}` ({ROUTER_IP})\n"
        f"• File: `{router_backup_file}`\n"
        f"• Size: `{size_kb:.1f} KB`\n"
        f"• Duration: `{duration}s`"
    )
else:
    alert_msg = (
        f"❌ *Backup GAGAL*\n\n"
        f"Router: `{router_name}` ({ROUTER_IP})\n"
        f"• Error: `{error_message}`\n"
        f"• Duration: `{duration}s`"
    )

try:
    send_telegram_markdown(alert_msg)
except Exception as tg_err:
    print(f"[!] Failed to send Telegram: {tg_err}")

# ==========================
# 6. CLEANUP OLD BACKUPS (7 days retention)
# ==========================
RETENTION_DAYS = 7
cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
deleted_count = 0

for root, dirs, files in os.walk(BASE_BACKUP_DIR):
    for file in files:
        path = os.path.join(root, file)
        try:
            if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                os.remove(path)
                deleted_count += 1
                print(f"[6] Deleted old backup: {path}")
        except Exception as del_err:
            print(f"[!] Failed to delete {path}: {del_err}")

if deleted_count > 0:
    print(f"[6] Cleanup: {deleted_count} old file(s) removed.")
else:
    print("[6] Cleanup: No old backups to remove.")

print(f"\nBackup process finished. Status: {status}")