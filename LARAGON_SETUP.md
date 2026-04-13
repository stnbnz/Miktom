# SETUP LARAGON DATABASE

## 1. Buka Laragon

```
C:\laragon\laragon.exe
```

## 2. Pastikan MySQL Running
- Klik tombol "Start All" atau
- Klik MySQL pada taskbar dan pastikan status GREEN

## 3. Buat Database untuk Project
Buka Laragon Terminal atau MySQL Client:

```bash
# Via Laragon MySQL Client
mysql -u root -p
# Tekan Enter (password kosong)

# Atau via command line
mysql -u root -h 127.0.0.1
```

Jalankan SQL:
```sql
CREATE DATABASE IF NOT EXISTS mikrotik_automation;
SHOW DATABASES; -- Verify database created
```

## 4. Konfigurasi Laragon di Django (SUDAH SESUAI)

File: `web_monitor/web_monitor/settings.py`

Sudah dikonfigurasi:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'mikrotik_automation',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}
```

## 5. Install MySQL Python Connector

```bash
# Activate virtual environment
source venv/Scripts/activate  # Linux/Mac
venv\Scripts\activate         # Windows PowerShell

# Install dependencies
pip install mysqlclient
# atau jika error, gunakan:
pip install PyMySQL
```

## 6. Run Django Migrations

```bash
cd web_monitor
python manage.py migrate
```

Output yang diharapkan:
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, dashboard, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
```

## 7. Verifikasi Database Connection

```bash
python manage.py dbshell
```

Jika berhasil akan membuka MySQL shell.

## 8. Create Django Superuser (Optional)

```bash
python manage.py createsuperuser
```

## 9. Test Scripts dengan Laragon Database

```bash
# Dari repo root
python device-tracker.py
python monitor-router.py
python backup.py <ROUTER_IP> <USERNAME> <PASSWORD>
python speedtest-logger.py
python daily-report.py
```

## Troubleshooting

### Error: "No such file or directory: 'mysql'"
- Install MySQL client atau gunakan PyMySQL
- `pip install PyMySQL`

### Error: "Can't connect to MySQL server"
- Verifi Laragon MySQL running (lihat taskbar icon harus GREEN)
- Verifikasi host: 127.0.0.1 (localhost)
- Verifikasi port: 3306 (default)
- Cek ulang password: kosong untuk root user

### Error: "Unknown database 'mikrotik_automation'"
- Jalankan SQL: `CREATE DATABASE mikrotik_automation;`

### Error pada manage.py migrate
- Pastikan MySQL sudah running
- Pastikan mysqlclient atau PyMySQL sudah installed
- Check settings.py DATABASES sudah benar

## Laragon Fitur Berguna

### Akses MySQL GUI
- Klik tombol "Database" di Laragon toolbar
- Atau buka HeidiSQL dari Laragon menu

### Check MySQL Status
- Klik tray icon Laragon
- Lihat MySQL status (harus RUNNING)

### Database Backup
Via HeidiSQL atau command line:
```bash
mysqldump -u root mikrotik_automation > backup.sql
```

### Restore Database
```bash
mysql -u root mikrotik_automation < backup.sql
```

## Notes
- Laragon MySQL user default: `root`
- Laragon MySQL password default: (kosong)
- Laragon MySQL host: `127.0.0.1` atau `localhost`
- Laragon MySQL port: `3306`
- Database name untuk project: `mikrotik_automation`
