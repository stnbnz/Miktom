"""
Setup Laragon Database for MikroTik Automation
Run this script once to initialize the database
"""
import os
import sys
import subprocess
from pathlib import Path

print("="*70)
print("  LARAGON DATABASE SETUP - MikroTik Automation Project")
print("="*70)

# Step 1: Check if Laragon MySQL is running
print("\n[1/5] Checking Laragon MySQL connection...")
try:
    import MySQLdb
    conn = MySQLdb.connect(
        host='127.0.0.1',
        user='root',
        password='',
        port=3306
    )
    conn.close()
    print("✅ Laragon MySQL is running and accessible")
except ImportError:
    print("❌ MySQLdb not installed")
    print("   Installing dependencies...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=False)
except Exception as e:
    print(f"❌ Cannot connect to Laragon MySQL")
    print(f"   Error: {e}")
    print("\n💡 Solusi:")
    print("   1. Buka Laragon dari C:\\laragon\\laragon.exe")
    print("   2. Klik 'Start All' o Click mysql taskbar icon untuk ensure MySQL running")
    print("   3. Jalankan script ini lagi")
    sys.exit(1)

# Step 2: Create database
print("\n[2/5] Creating database 'mikrotik_automation'...")
try:
    import MySQLdb
    conn = MySQLdb.connect(
        host='127.0.0.1',
        user='root',
        password='',
        port=3306
    )
    cursor = conn.cursor()
    
    # Create database with utf8mb4
    cursor.execute(f"""
        CREATE DATABASE IF NOT EXISTS mikrotik_automation 
        CHARACTER SET utf8mb4 
        COLLATE utf8mb4_unicode_ci;
    """)
    
    # Verify
    cursor.execute("SHOW DATABASES LIKE 'mikrotik_automation'")
    if cursor.fetchone():
        print("✅ Database created successfully")
    else:
        print("❌ Failed to create database")
        sys.exit(1)
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"❌ Error creating database: {e}")
    sys.exit(1)

# Step 3: Setup Django environment
print("\n[3/5] Setting up Django environment...")
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
    
    # Add paths
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    sys.path.insert(0, os.path.join(project_root, 'web_monitor'))
    
    import django
    django.setup()
    print("✅ Django environment configured")
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

# Step 4: Run migrations
print("\n[4/5] Running Django migrations...")
try:
    os.chdir(os.path.join(project_root, 'web_monitor'))
    result = subprocess.run(
        [sys.executable, 'manage.py', 'migrate'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Migrations completed successfully")
        # Show migration summary
        if "Operations to perform:" in result.stdout:
            print("   Migrations applied:")
            for line in result.stdout.split('\n'):
                if 'Applying' in line:
                    print(f"   {line.strip()}")
    else:
        print(f"❌ Migration failed")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
except Exception as e:
    print(f"❌ Error during migrations: {e}")
    sys.exit(1)

# Step 5: Create superuser (optional)
print("\n[5/5] Verifying database connection...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("✅ Database connection verified")
    
    # Check tables
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = 'mikrotik_automation'
        """)
        table_count = cursor.fetchone()[0]
    print(f"✅ Database tables created: {table_count} tables")
    
except Exception as e:
    print(f"❌ Database verification failed: {e}")
    sys.exit(1)

# Final summary
print("\n" + "="*70)
print("  ✅ SETUP COMPLETE - Laragon Database Ready!")
print("="*70)
print("\nNext steps:")
print("  1. Create superuser (optional):")
print("     cd web_monitor && python manage.py createsuperuser")
print("\n  2. Run scripts:")
print("     python verify_laragon_connection.py  (to test connection)")
print("     python device-tracker.py")
print("     python monitor-router.py")
print("     python backup.py <IP> <USER> <PASSWORD>")
print("\n  3. Web Interface (optional):")
print("     cd web_monitor && python manage.py runserver")
print("     Access: http://localhost:8000/admin")
print("="*70)
