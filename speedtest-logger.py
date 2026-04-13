import subprocess
import json
import os
import sys
import django
from datetime import datetime

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from web_monitor.dashboard.models import SpeedtestLog
from alert import send_telegram

# ======================
# SLA CONFIGURATION
# ======================
SLA_DOWNLOAD_MIN_MBPS = 20.0  # Alert if download speed under 20 Mbps
SLA_UPLOAD_MIN_MBPS = 10.0    # Alert if upload speed under 10 Mbps
SLA_MAX_PING = 100            # Alert if ping is over 100ms

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
    # LOG TO DJANGO DATABASE
    # ==========================
    try:
        SpeedtestLog.objects.create(
            test_time=datetime.now(),
            ping=ping_ms,
            download=download_mbps,
            upload=upload_mbps,
            server_name='speedtest-cli'
        )
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
        try:
            send_telegram(alert_msg)
        except Exception as e:
            print(f"Failed to send alert: {e}")
    else:
        print("\nInternet speed is optimal. No SLA breach.")

except Exception as e:
    print("Error:", e)
