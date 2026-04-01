import routeros_api
import subprocess
import json
import os
import mysql.connector
from datetime import datetime, date

# ==========================
# MYSQL CONFIG
# ==========================
DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_PASS = ""
DB_NAME = "mikrotik_automation"

# ======================
# FILES TO ANALYZE
# ======================
DEVICES_FILE = "known_devices.json"
FAILOVER_FILE = "failover_state.json"
QOS_FILE = "qos_state.json"

print("================================")
print(" MikroTik Daily Network Reporter")
print(" Time:", datetime.now())
print("================================")

report = f"📊 *DAILY NETWORK REPORT*\nDate: {date.today()}\n\n"

# 1. Total Active Devices
try:
    if os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, "r") as f:
            devices = json.load(f)
            total_devices = len(devices)
            
            # Count recently seen today
            today_str = str(date.today())
            new_today = sum(1 for v in devices.values() if today_str in v.get("first_seen", ""))
            
            report += f"📱 *Devices*\n"
            report += f"Total historical devices: {total_devices}\n"
            report += f"New devices today: {new_today}\n\n"
    else:
        report += "📱 *Devices*: Tracking data not available.\n\n"
except Exception as e:
    print("Error analyzing devices:", e)

# 2. Avg Internet Speed
try:
    db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS speedtest_log (
            id INT AUTO_INCREMENT PRIMARY KEY, 
            test_time DATETIME, 
            ping FLOAT, 
            download FLOAT, 
            upload FLOAT
        )
    """)

    # Calculate average speed for today
    sql = "SELECT AVG(download), AVG(upload), AVG(ping) FROM speedtest_log WHERE DATE(test_time) = CURDATE()"
    cursor.execute(sql)
    row = cursor.fetchone()
    
    if row and row[0] is not None:
        avg_down, avg_up, avg_ping = row
        report += "🌐 *Internet Speed (Avg Today)*\n"
        report += f"Download: {avg_down:.2f} Mbps\n"
        report += f"Upload  : {avg_up:.2f} Mbps\n"
        report += f"Latency : {avg_ping:.2f} ms\n\n"
    else:
        report += "🌐 *Internet Speed*: No speed tests run today.\n\n"
        
    db.close()
except Exception as e:
    report += "🌐 *Internet Speed*: Database not reachable.\n\n"
    print("Error analyzing speed:", e)

# 3. System States
try:
    report += "⚙️ *System Health*\n"
    
    # Failover state
    if os.path.exists(FAILOVER_FILE):
        with open(FAILOVER_FILE, "r") as f:
            f_state = json.load(f)
            report += f"- Active connection: {f_state.get('active_wan', 'Unknown')}\n"
            
    # QoS state
    if os.path.exists(QOS_FILE):
        with open(QOS_FILE, "r") as f:
            q_state = json.load(f)
            status = "Activated (Throttled)" if q_state.get('is_throttled') else "Normal"
            report += f"- Smart QoS Status: {status}\n"
            
    report += "\n"
except Exception as e:
    print("Error analyzing states:", e)

# Final Touches
report += "Semua sistem berjalan normal! ✨"

print(report)
print("\nSending Daily Report via WhatsApp...")

try:
    subprocess.run([
        "python3",
        "alert.py",
        report
    ])
    print("Daily Report sent successfully.")
except Exception as e:
    print("Failed to send report:", e)
