import routeros_api
import paramiko
import mysql.connector
import os
import time
from datetime import datetime, timedelta

# ==========================
# ROUTER CONFIG
# ==========================

ROUTER_IP = "192.168.1.2"
USERNAME = "admin"
PASSWORD = ""

# ==========================
# MYSQL CONFIG
# ==========================

DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_PASS = ""
DB_NAME = "mikrotik_automation"

# ==========================
# BACKUP FOLDER
# ==========================

BASE_BACKUP_DIR = "/home/stnbnz/miktom/mikrotik-backup"

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
# LOG TO MYSQL
# ==========================

try:

    db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )

    cursor = db.cursor()

    sql = """
    INSERT INTO backup_log
    (router_ip, backup_time, backup_file, status)
    VALUES (%s,%s,%s,%s)
    """

    cursor.execute(sql, (
        ROUTER_IP,
        now,
        router_backup_file,
        status
    ))

    db.commit()

    print("Log saved to database")

except Exception as e:
    print("DB error:", e)

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