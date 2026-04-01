import subprocess
import json
import os
import sys
import mysql.connector
from datetime import datetime

# ======================
# SLA CONFIGURATION
# ======================
SLA_DOWNLOAD_MIN_MBPS = 20.0  # Alert if download speed under 20 Mbps
SLA_UPLOAD_MIN_MBPS = 10.0    # Alert if upload speed under 10 Mbps
SLA_MAX_PING = 100            # Alert if ping is over 100ms

# ==========================
# MYSQL CONFIG
# ==========================
DB_HOST = "127.0.0.1"
DB_USER = "root"
DB_PASS = ""
DB_NAME = "mikrotik_automation"

print("================================")
print(" MikroTik Speedtest & SLA Logger")
print(" Time:", datetime.now())
print("================================")

try:
    # Run speedtest-cli and get JSON output
    print("Running bandwidth test (this may take a minute)...")
    result = subprocess.run(
        [sys.executable, "-m", "speedtest", "--json"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True
    )
    
    if result.returncode != 0:
        print("Speedtest failed. Is speedtest-cli installed?")
        print("Hint: pip install speedtest-cli")
        sys.exit(1)

    data = json.loads(result.stdout)
    
    # Convert bits per second to Megabits per second
    download_mbps = data["download"] / 1_000_000
    upload_mbps = data["upload"] / 1_000_000
    ping_ms = data["ping"]
    
    print("\n=== TEST RESULTS ===")
    print(f"Ping     : {ping_ms:.2f} ms")
    print(f"Download : {download_mbps:.2f} Mbps")
    print(f"Upload   : {upload_mbps:.2f} Mbps")
    
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS speedtest_log (
                id INT AUTO_INCREMENT PRIMARY KEY, 
                test_time DATETIME, 
                ping FLOAT, 
                download FLOAT, 
                upload FLOAT
            )
        """)

        sql = "INSERT INTO speedtest_log (test_time, ping, download, upload) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (datetime.now(), ping_ms, download_mbps, upload_mbps))
        db.commit()
        db.close()
        print("\nResults logged to database.")
    except Exception as db_err:
        print("\nFailed to log to database:", db_err)

    # ==========================
    # SLA BREACH CHECK
    # ==========================
    alerts = []
    
    if download_mbps < SLA_DOWNLOAD_MIN_MBPS:
        alerts.append(f"🔻 Download Speed ({download_mbps:.2f} Mbps) < SLA ({SLA_DOWNLOAD_MIN_MBPS} Mbps)")
        
    if upload_mbps < SLA_UPLOAD_MIN_MBPS:
        alerts.append(f"🔻 Upload Speed ({upload_mbps:.2f} Mbps) < SLA ({SLA_UPLOAD_MIN_MBPS} Mbps)")
        
    if ping_ms > SLA_MAX_PING:
        alerts.append(f"⚠️ High Latency ({ping_ms:.2f} ms) > SLA ({SLA_MAX_PING} ms)")

    if alerts:
        alert_msg = "📉 *INTERNET SLA BREACH DETECTED*\n\n"
        alert_msg += "Current Internet quality is below standard:\n"
        for alert in alerts:
            alert_msg += f"- {alert}\n"
            
        print("\nSLA Breach detected. Sending Alert...")
        subprocess.run([
            "python3",
            "alert.py",
            alert_msg
        ])
    else:
        print("\nInternet speed is optimal. No SLA breach.")

except Exception as e:
    print("Error:", e)
