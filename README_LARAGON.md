# MikroTik Automation Project - Laragon Database Setup

**Project ini menggunakan Laragon sebagai database MySQL untuk semua automation scripts.**

## Quick Start (5 Menit)

### 1. Pastikan Laragon Sudah Installed
- Download dari: https://laragon.org/
- Install di `C:\laragon` (default)
- Buka `C:\laragon\laragon.exe`

### 2. Jalankan Setup Script (HANYA SEKALI)

```bash
# Buka PowerShell atau Command Prompt
cd d:\Project\miktom

# Activate virtual environment
venv\Scripts\activate

# Run setup
python setup_laragon_database.py
```

**Output yang diharapkan:**
```
✅ Laragon MySQL is running and accessible
✅ Database created successfully
✅ Django environment configured
✅ Migrations completed successfully
✅ Database connection verified
✅ SETUP COMPLETE - Laragon Database Ready!
```

### 3. Verify Koneksi

```bash
python verify_laragon_connection.py
```

Jika semua OK, lanjut ke step 4.

### 4. Jalankan Scripts

```bash
# Add router to database (hanya sekali)
python setup-mikrotik.py 192.168.1.2 admin password123

# Atau set default router sebagai active
# Di web interface atau direct database query

# Jalankan automation scripts
python device-tracker.py
python monitor-router.py
python failover-wan.py
python security-shield.py
python smart-qos.py
python speedtest-logger.py
python daily-report.py
python backup.py 192.168.1.2 admin password123
```

---

## Konfigurasi Detail

### Database Configuration

Laragon MySQL default:
- **Host**: `127.0.0.1` (localhost)
- **Port**: `3306`
- **User**: `root`
- **Password**: (kosong)
- **Database**: `mikrotik_automation`

Django settings (`web_monitor/web_monitor/settings.py`):
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'mikrotik_automation',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

### Virtual Environment

```bash
# Create (jika belum ada)
python -m venv venv

# Activate
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables (.env)

File `.env` (opsional, untuk override default):
```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=mikrotik_automation
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
DEBUG=True
TIME_ZONE=Asia/Jakarta
```

---

## Database Models Overview

### Core Models
- **Router**: Nama, IP, username, password, status aktif
- **ActivityLog**: Audit trail semua aktivitas
- **BackupLog**: History backup files

### Device & Network
- **TrackedDevice**: Device yang terdeteksi di network
- **SystemMetrics**: CPU, RAM, internet status
- **ActiveUser**: User yang sedang online
- **NetworkTraffic**: Data traffic per interface

### Failover & Security
- **FailoverState**: State current WAN failover
- **FailoverEvent**: History failover events
- **SecurityEvent**: IP bans dan security incidents

### Speed & System
- **SpeedtestLog**: History speed test results
- **SystemAlert**: System alerts
- **VoucherUsage**: Voucher usage tracking

---

## Mengelola Database

### Via Laragon GUI
1. Buka Laragon
2. Klik "Database" button
3. Pilih "HeidiSQL" atau "MySQL Workbench"
4. Connect to `localhost` with user `root`

### Via Command Line

```bash
# Connect ke MySQL
mysql -u root -h 127.0.0.1

# Jalankan queries
mysql -u root -h 127.0.0.1 -e "SELECT * FROM mikrotik_automation.dashboard_router;"

# Backup
mysqldump -u root mikrotik_automation > backup.sql

# Restore
mysql -u root mikrotik_automation < backup.sql
```

### Via Django Shell

```bash
cd web_monitor
python manage.py shell

>>> from dashboard.models import Router, ActivityLog
>>> Router.objects.all()
>>> ActivityLog.objects.count()
>>> # Query data
```

---

## Troubleshooting

### ❌ Error: "Can't connect to MySQL server"

**Solusi:**
1. Pastikan Laragon running
   - Buka `C:\laragon\laragon.exe`
   - Klik "Start All"
   - Lihat MySQL di taskbar harus RUNNING (icon green)

2. Test MySQL di PowerShell:
   ```bash
   mysql -u root -h 127.0.0.1
   ```
   Jika tidak bisa, MySQL tidak running.

3. Cek port 3306 tidak terpakai:
   ```bash
   netstat -nan | findstr :3306
   ```

### ❌ Error: "Unknown database 'mikrotik_automation'"

**Solusi:**
```bash
# Jalankan setup lagi
python setup_laragon_database.py

# Atau manual create
mysql -u root -h 127.0.0.1 -e "CREATE DATABASE IF NOT EXISTS mikrotik_automation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### ❌ Error: "ModuleNotFoundError: No module named 'MySQLdb'"

**Solusi:**
```bash
pip install -r requirements.txt

# Atau install specific
pip install mysqlclient
# Jika error di Windows, gunakan:
pip install PyMySQL
```

### ❌ Error pada "migrate"

**Solusi:**
1. Pastikan database sudah created
2. Pastikan koneksi MySQL OK
3. Delete semua `.pyc` files:
   ```bash
   Get-ChildItem -Recurse -Include *.pyc | Remove-Item
   ```
4. Jalankan migrate lagi:
   ```bash
   cd web_monitor
   python manage.py migrate --verbosity 2
   ```

### ❌ "Script says database connection OK tapi migrations failed"

**Solusi:**
1. Check Django settings:
   ```bash
   cd web_monitor
   python manage.py dbshell
   ```

2. Check migrations status:
   ```bash
   python manage.py showmigrations
   ```

3. Run specific migration:
   ```bash
   python manage.py migrate dashboard
   ```

---

## Script-by-Script Usage

### device-tracker.py
Detects new devices pada network hotspot

```bash
python device-tracker.py
```
Menyimpan ke: `TrackedDevice` model

### monitor-router.py
Monitor CPU, RAM, internet, interface status

```bash
python monitor-router.py
# atau dengan specific router:
python monitor-router.py 192.168.1.2 admin password123
```
Menyimpan ke: `SystemMetrics` model

### failover-wan.py
Monitor WAN failover ISP1 <-> ISP2

```bash
python failover-wan.py
```
Menyimpan ke: `FailoverState` + `FailoverEvent` models

### security-shield.py
Ban IPs dengan failed login attempts

```bash
python security-shield.py
```
Menyimpan ke: `SecurityEvent` model

### smart-qos.py
Auto-throttle WiFi-Guest queue saat network saturated

```bash
python smart-qos.py
```
Menyimpan ke: `ActivityLog` dengan type `qos_change`

### speedtest-logger.py
Run speedtest dan catat hasil

```bash
python speedtest-logger.py
```
Menyimpan ke: `SpeedtestLog` model

### daily-report.py
Generate laporan harian dan kirim via Telegram

```bash
python daily-report.py
```
Membaca dari: semua models

### backup.py
Backup router config via SFTP

```bash
python backup.py 192.168.1.2 admin password123
```
Menyimpan ke: `BackupLog` + `ActivityLog` models

---

## Running di Production

### Gunakan Environment Variables

```env
# .env
DB_ENGINE=django.db.backends.mysql
DB_NAME=mikrotik_automation
DB_USER=production_user
DB_PASSWORD=strong_password_123
DB_HOST=192.168.1.100
DB_PORT=3306
DEBUG=False
```

### Create Production MySQL User

```sql
-- Di Laragon MySQL
CREATE USER 'production_user'@'%' IDENTIFIED BY 'strong_password_123';
GRANT ALL PRIVILEGES ON mikrotik_automation.* TO 'production_user'@'%';
FLUSH PRIVILEGES;
```

### Setup Cron Jobs (Linux/WSL)

```bash
# Every 5 minutes
*/5 * * * * /path/to/venv/bin/python /path/to/device-tracker.py

# Every minute (speedtest once per hour dalam script)
* * * * * /path/to/venv/bin/python /path/to/speedtest-logger.py

# Every hour
0 * * * * /path/to/venv/bin/python /path/to/monitor-router.py

# Daily (6 AM)
0 6 * * * /path/to/venv/bin/python /path/to/backup.py 192.168.1.2 admin pass

# Daily report (7 AM)
0 7 * * * /path/to/venv/bin/python /path/to/daily-report.py
```

### Windows Task Scheduler

1. Buka Task Scheduler
2. New Basic Task
3. Trigger: Daily / Hourly / etc
4. Action: `python "D:\Project\miktom\device-tracker.py"`
5. Start in: `D:\Project\miktom`

---

## Database Maintenance

### Backup Database Reguler

```bash
# Manual backup
mysqldump -u root mikrotik_automation > "backup_$(date +%Y%m%d_%H%M%S).sql"

# Compressed backup
mysqldump -u root mikrotik_automation | gzip > backup.sql.gz
```

### Clean Old Data

```python
# Via Django shell
from django.utils import timezone
from datetime import timedelta
from dashboard.models import ActivityLog

# Delete ActivityLog older than 90 days
cutoff = timezone.now() - timedelta(days=90)
ActivityLog.objects.filter(timestamp__lt=cutoff).delete()
```

### Monitor Database Size

```bash
# Check database size
mysql -u root -e "SELECT table_schema, SUM(data_length + index_length) / 1024 / 1024 AS size_mb FROM information_schema.TABLES GROUP BY table_schema;"
```

---

## Need Help?

1. Check LARAGON_SETUP.md for detailed Laragon setup
2. Check DATABASE_STANDARDIZATION.md untuk database models
3. Run `python verify_laragon_connection.py` untuk diagnose
4. Check web_monitor/dashboard/models.py untuk available models

---

**Last Updated**: April 2026
**Tested with**: Python 3.8+, Django 6.0.3, Laragon latest
