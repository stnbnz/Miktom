# Cron Automation Guide

Panduan ini untuk menjalankan automation secara terjadwal dan menjaga database tetap sehat.

## 1) Jalankan migrasi dulu

```bash
py manage.py migrate
```

## 2) Jalankan automation manual (uji coba)

```bash
py manage.py run_automation --run-scripts --retention-days 14
```

Perintah ini akan:
- sinkron voucher (`expire_vouchers`)
- membersihkan data monitoring lama
- menjalankan script otomasi utama (`monitor-router.py`, `device-tracker.py`, dll)
- menyimpan hasil ke tabel `dashboard_automationrunlog`

## 3) Rebuild database (opsional, destructive)

Gunakan hanya jika Anda benar-benar ingin reset total data:

```bash
py manage.py rebuild_database --yes-i-know
```

## 4) Jadwalkan via Cron (Linux)

Contoh setiap 5 menit:

```cron
*/5 * * * * cd /path/to/miktom/web_monitor && /usr/bin/python3 manage.py run_automation --run-scripts --retention-days 14 >> /var/log/miktom-automation.log 2>&1
```

## 5) Jadwalkan di Windows (Task Scheduler)

Program/script:
- `py`

Arguments:
- `manage.py run_automation --run-scripts --retention-days 14`

Start in:
- `D:\Project\miktom\web_monitor`

## 6) Endpoint health

Gunakan endpoint berikut untuk cek status sistem + status automation terakhir:

- `/api/system_health`
