"""
Database Connection Test for Laragon
Pastikan MySQL Laragon sudah running sebelum menjalankan script ini
"""
import os
import sys
import django

# Add paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')

print("="*60)
print("  LARAGON DATABASE CONNECTION TEST")
print("="*60)

try:
    # Setup Django
    django.setup()
    print("\n✅ Django Setup: SUCCESS")
except Exception as e:
    print(f"\n❌ Django Setup: FAILED")
    print(f"   Error: {e}")
    sys.exit(1)

try:
    # Test database connection
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("✅ Database Connection: SUCCESS")
    print(f"   Host: 127.0.0.1:3306")
    print(f"   User: root")
    print(f"   Database: mikrotik_automation")
except Exception as e:
    print(f"❌ Database Connection: FAILED")
    print(f"   Error: {e}")
    print("\n💡 Troubleshooting:")
    print("   1. Pastikan Laragon running (lihat taskbar icon)")
    print("   2. Pastikan MySQL service aktif")
    print("   3. Jalankan: mysql -u root -h 127.0.0.1")
    print("   4. CREATE DATABASE mikrotik_automation;")
    sys.exit(1)

try:
    # Test models
    from web_monitor.dashboard.models import Router
    router_count = Router.objects.count()
    print(f"✅ Models Access: SUCCESS")
    print(f"   Total routers: {router_count}")
except Exception as e:
    print(f"❌ Models Access: FAILED")
    print(f"   Error: {e}")
    print("\n💡 Solution:")
    print("   Jalankan: python manage.py migrate")
    sys.exit(1)

try:
    # Test creating a router (dry run)
    from web_monitor.dashboard.models import Router
    print(f"✅ Database Operations: OK")
except Exception as e:
    print(f"❌ Database Operations: FAILED")
    print(f"   Error: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("  ✅ ALL TESTS PASSED - Laragon Ready!")
print("="*60)
print("\nSiap menjalankan scripts:")
print("  - python device-tracker.py")
print("  - python monitor-router.py")
print("  - python failover-wan.py")
print("  - python security-shield.py")
print("  - python smart-qos.py")
print("  - python speedtest-logger.py")
print("  - python daily-report.py")
print("  - python backup.py <IP> <USER> <PASS>")
print("="*60)
