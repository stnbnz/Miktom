# MikroTik Database Standardization Documentation

## Overview
Semua script automation di project ini telah distandarisasi untuk menggunakan **Django database** yang sama, menghilangkan dependency terhadap JSON files dan hardcoded credentials.

## Database Models Digunakan

### Core Models
- **Router**: Pusat konfigurasi - menyimpan IP, username, password, status aktif
- **ActivityLog**: Mencatat semua aktivitas sistem untuk audit trail
- **SpeedtestLog**: Hasil tes kecepatan internet
- **BackupLog**: Log backup router

### Device & Network Models
- **TrackedDevice**: Device yang terdeteksi di jaringan (menggantikan `known_devices.json`)
- **SystemMetrics**: Metrik sistem router (CPU, RAM, internet status)
- **ActiveUser**: User aktif di router
- **NetworkTraffic**: Data traffic per interface

### Failover & Security Models
- **FailoverState**: State current WAN failover per router
- **FailoverEvent**: Log event failover
- **SecurityEvent**: Log event security (IP ban, detections)

## Script-by-Script Changes

### 1. device-tracker.py
**Before**: Menyimpan state di `known_devices.json`
**After**: 
- Menggunakan Django database + Router model
- TrackedDevice model untuk track devices
- ActivityLog untuk mencatat device baru

```python
# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from web_monitor.dashboard.models import Router, TrackedDevice, ActivityLog

# Get active router dari database
router = Router.objects.filter(is_active=True).first()
```

### 2. monitor-router.py
**Before**: Menyimpan state di `router_state.json`
**After**:
- Menggunakan Django + sistemMetrics model
- Mencatat system metrics ke database
- ActivityLog untuk alert

```python
metrics = SystemMetrics.objects.create(
    router=router,
    cpu_load=cpu_load,
    ram_usage=ram_usage,
    internet_status=internet_status
)
```

### 3. failover-wan.py
**Before**: Menyimpan state di `failover_state.json`
**After**:
- FailoverState model untuk state management
- FailoverEvent model untuk mencatat setiap failover/restore
- ActivityLog untuk audit trail

```python
failover_state, _ = FailoverState.objects.get_or_create(router=router)
FailoverEvent.objects.create(
    router=router,
    previous_wan='ISP1_ACTIVE',
    new_wan='ISP2_ACTIVE',
    event_type='failover'
)
```

### 4. security-shield.py
**Before**: Tidak menggunakan database
**After**:
- SecurityEvent model untuk mencatat IP bans
- ActivityLog untuk mencatat security events
- Router credentials dari database

```python
SecurityEvent.objects.create(
    router=router,
    ip_address=ip,
    failure_count=count,
    action='banned',
    ban_duration='1d'
)
```

### 5. smart-qos.py
**Before**: Menyimpan state di `qos_state.json`
**After**:
- ActivityLog model dengan activity_type='qos_change' untuk track QoS state
- Node metadata menyimpan state detail

```python
ActivityLog.objects.create(
    router=router,
    activity_type='qos_change',
    description=f'Smart QoS activated',
    metadata={'queue': QUEUE_NAME, 'limit': THROTTLED_LIMIT}
)
```

### 6. speedtest-logger.py
**Status**: Sudah menggunakan Django database
**Optimasi**: Tidak ada perubahan major, sudah optimal

### 7. daily-report.py
**Before**: Membaca dari JSON files
**After**:
- Menggunakan Django ORM untuk query database
- TrackedDevice untuk device count
- SpeedtestLog untuk speed stats
- FailoverState dan FailoverEvent untuk failover info
- SecurityEvent untuk security event count

```python
total_devices = TrackedDevice.objects.filter(router=router).count()
speeds = SpeedtestLog.objects.filter(router=router, test_time__date=today).aggregate(
    avg_download=Avg('download'),
    avg_upload=Avg('upload'),
    avg_ping=Avg('ping')
)
```

### 8. setup-mikrotik.py
**Before**: Hardcoded router credentials
**After**:
- Bisa accept router credentials via command line atau dari database
- Menyimpan router ke database
- ActivityLog untuk mencatat setup completion

```python
router, _ = Router.objects.get_or_create(
    ip_address=ROUTER_IP,
    defaults={'name': f'Router_{ROUTER_IP}', 'username': USERNAME, 'password': PASSWORD}
)
```

## Django Setup Pattern

Semua script sekarang menggunakan pattern yang konsisten:

```python
import sys
import os
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

# Now import models
from web_monitor.dashboard.models import Router, ActivityLog, ...
```

### Alternative: Menggunakan django_bootstrap.py
```python
from django_bootstrap import setup_django, get_router
setup_django()
router = get_router()  # Get active router or first router
```

## Environment Setup

Pastikan database sudah siap:

```bash
cd web_monitor
python manage.py migrate
```

## Running Scripts

### Dengan Active Router di Database
```bash
python device-tracker.py
python monitor-router.py
python failover-wan.py
python security-shield.py
python smart-qos.py
python speedtest-logger.py
python daily-report.py
```

### Setup atau Custom Router
```bash
python setup-mikrotik.py 192.168.1.2 admin password123
python monitor-router.py 192.168.1.2 admin password123
```

## Migration Dari Legacy System

Jika memiliki legacy JSON files, import data ke database:

```python
# Import TrackedDevice dari known_devices.json
import json
from web_monitor.dashboard.models import Router, TrackedDevice

router = Router.objects.first()
with open('known_devices.json') as f:
    devices = json.load(f)
    for mac, data in devices.items():
        TrackedDevice.objects.get_or_create(
            router=router,
            mac_address=mac,
            defaults={
                'hostname': data.get('hostname'),
                'ip_address': data.get('ip')
            }
        )
```

## Advantages of Standardization

1. **Centralized Data**: Semua data di database, tidak tersebar di JSON files
2. **Audit Trail**: Semua aktivitas tercatat di ActivityLog
3. **Consistency**: Semua script menggunakan model yang sama
4. **Security**: Credentials tersimpan terenkripsi di database
5. **Scalability**: Mudah untuk menambah router baru
6. **Query Capability**: Bisa query data dari web interface
7. **No File Management**: Tidak perlu manage JSON files
8. **Historical Data**: Bisa track historical changes dan trends

## Monitoring & Maintenance

### Check Recent Activities
```python
from web_monitor.dashboard.models import ActivityLog
from django.utils import timezone
from datetime import timedelta

# Last 1 hour activities
recent = ActivityLog.objects.filter(
    timestamp__gte=timezone.now() - timedelta(hours=1)
).order_by('-timestamp')
```

### Check Failover History
```python
from web_monitor.dashboard.models import FailoverEvent

failovers = FailoverEvent.objects.filter(
    router__name='Router_Main'
).order_by('-timestamp')[:10]
```

### Check Security Events
```python
from web_monitor.dashboard.models import SecurityEvent

today_bans = SecurityEvent.objects.filter(
    action='banned',
    timestamp__date=timezone.now().date()
).values('ip_address').distinct()
```

## Notes

- Semua script memerlukan `web_monitor/settings.py` dan database Django yang sudah configured
- Backup.py tetap unchanged karena sudah menggunakan database
- Alert.py tetap berperan sebagai utility untuk kirim Telegram
- Jalankan `python manage.py makemigrations && python manage.py migrate` jika ada perubahan model
