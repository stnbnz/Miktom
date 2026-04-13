import routeros_api
import paramiko
import os
import time
import sys
import django
from datetime import datetime, timedelta

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from web_monitor.dashboard.models import Router, BackupLog, ActivityLog

# ==========================
# COMMAND LINE ARGUMENTS
# ==========================

if len(sys.argv) < 4:
    print("Usage: python backup.py <ROUTER_IP> <USERNAME> <PASSWORD>")
    sys.exit(1)

ROUTER_IP = sys.argv[1]
USERNAME = sys.argv[2]
PASSWORD = sys.argv[3]

# ==========================
# BACKUP FOLDER
# ==========================

BASE_BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mikrotik-backup"))

# ==========================
# TIME
# ==========================

now = datetime.now()
date_folder = now.strftime("%Y-%m-%d")
timestamp = now.strftime("%Y%m%d_%H%M")

backup_name = f"backup_{timestamp}"
export_name = f"export_{timestamp}"

router_backup_file = backup_name + ".backup"
router_export_file = export_name + ".rsc"

# ==========================
# LOCAL FOLDER
# ==========================

local_dir = f"{BASE_BACKUP_DIR}/{ROUTER_IP}/{date_folder}"
os.makedirs(local_dir, exist_ok=True)

local_backup = f"{local_dir}/{router_backup_file}"
local_export = f"{local_dir}/{router_export_file}"

status = "FAILED"
error_message = ""
start_time = time.time()

try:

    # ==========================
    # CONNECT API (CREATE BINARY BACKUP)
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

    print("Binary backup created")

    # ==========================
    # SSH EXPORT CONFIG
    # ==========================

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(ROUTER_IP, username=USERNAME, password=PASSWORD)

    ssh.exec_command(f"/export file={export_name}")

    ssh.close()

    print("Export config created")

    # tunggu router membuat file
    time.sleep(5)

    # ==========================
    # DOWNLOAD FILE VIA SFTP
    # ==========================

    transport = paramiko.Transport((ROUTER_IP, 22))
    transport.connect(username=USERNAME, password=PASSWORD)

    sftp = paramiko.SFTPClient.from_transport(transport)

    files = sftp.listdir()

    if router_backup_file in files:
        sftp.get(router_backup_file, local_backup)
        print("Binary backup downloaded")

    if router_export_file in files:
        sftp.get(router_export_file, local_export)
        print("Export config downloaded")

    sftp.close()
    transport.close()

    status = "SUCCESS"

except Exception as e:
    print("Error:", e)

# ==========================
# LOG TO DJANGO DATABASE
# ==========================

try:
    # Get router from database
    router = Router.objects.filter(ip_address=ROUTER_IP).first()
    if not router:
        print("Warning: Router not found in database, creating backup log without router reference")
        router = None
    
    # Calculate file sizes
    backup_size = os.path.getsize(local_backup) if os.path.exists(local_backup) else 0
    export_size = os.path.getsize(local_export) if os.path.exists(local_export) else 0
    total_size = backup_size + export_size
    
    # Calculate duration
    duration = int(time.time() - start_time)
    
    # Create backup log entry
    backup_log = BackupLog.objects.create(
        router=router,
        backup_time=now,
        backup_file=router_backup_file,
        status=status,
        file_size=total_size,
        duration=duration
    )
    
    # Log activity
    if router:
        ActivityLog.objects.create(
            router=router,
            activity_type='backup_manual',
            description=f'Automatic backup completed - {status}',
            metadata={
                'backup_file': router_backup_file,
                'export_file': router_export_file,
                'backup_size': backup_size,
                'export_size': export_size,
                'total_size': total_size,
                'duration_seconds': duration,
                'status': status
            },
            success=(status == 'SUCCESS'),
            error_message=error_message
        )
    
    print("Log saved to Django database")

except Exception as e:
    print("DB error:", e)
    error_message = str(e)

# ==========================
# CLEANUP OLD BACKUPS
# ==========================

RETENTION_DAYS = 7
cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)

for root, dirs, files in os.walk(BASE_BACKUP_DIR):

    for file in files:

        path = os.path.join(root, file)

        if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:

            os.remove(path)
            print("Deleted old backup:", path)