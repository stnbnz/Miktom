import routeros_api
import sys
import os
import django
from datetime import datetime, date, timedelta

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import (
    SpeedtestLog, TrackedDevice, FailoverState, ActivityLog, 
    SystemMetrics, FailoverEvent, Router
)
from django.db.models import Avg, Count
from django.utils import timezone

try:
    from alert import send_telegram
except ImportError:
    def send_telegram(msg): 
        print("[alert] send_telegram not available:", msg)

print("================================")
print(" MikroTik Daily Network Reporter")
print(" Time:", datetime.now())
print("================================")

# Get active router or first router
router = Router.objects.filter(is_active=True).first() or Router.objects.first()

if not router:
    print("Error: No router found in database")
    sys.exit(1)

report = f"📊 *DAILY NETWORK REPORT*\nDate: {date.today()}\nRouter: {router.name}\n\n"

# 1. Total Active Devices
try:
    total_devices = TrackedDevice.objects.filter(router=router).count()
    new_today = TrackedDevice.objects.filter(
        router=router,
        first_seen__date=date.today()
    ).count()
    
    report += f"📱 *Devices*\n"
    report += f"Total tracked devices: {total_devices}\n"
    report += f"New devices today: {new_today}\n\n"
except Exception as e:
    report += "📱 *Devices*: Database error.\n\n"
    print(f"Error analyzing devices: {e}")

# 2. Avg Internet Speed
try:
    today = timezone.now().date()
    
    speeds = SpeedtestLog.objects.filter(
        router=router,
        test_time__date=today
    ).aggregate(
        avg_download=Avg('download'),
        avg_upload=Avg('upload'),
        avg_ping=Avg('ping'),
        test_count=Count('id')
    )
    
    if speeds['avg_download'] is not None:
        report += "🌐 *Internet Speed (Daily Average)*\n"
        report += f"Download: {speeds['avg_download']:.2f} Mbps\n"
        report += f"Upload  : {speeds['avg_upload']:.2f} Mbps\n"
        report += f"Latency : {speeds['avg_ping']:.2f} ms\n"
        report += f"Tests run: {speeds['test_count']}\n\n"
    else:
        report += "🌐 *Internet Speed*: No speed tests today.\n\n"
except Exception as e:
    report += "🌐 *Internet Speed*: Database error.\n\n"
    print(f"Error analyzing speed: {e}")

# 3. System Health & States
try:
    report += "⚙️ *System Health*\n"
    
    # Failover state
    failover_state = FailoverState.objects.filter(router=router).first()
    if failover_state:
        report += f"- Active WAN: {failover_state.active_wan}\n"
        
    # Recent system metrics
    latest_metrics = SystemMetrics.objects.filter(router=router).order_by('-timestamp').first()
    if latest_metrics:
        report += f"- CPU Load: {latest_metrics.cpu_load}%\n"
        report += f"- RAM Usage: {latest_metrics.ram_usage}%\n"
        report += f"- Internet: {latest_metrics.internet_status}\n"
    
    # Failover events today
    failover_events_today = FailoverEvent.objects.filter(
        router=router,
        timestamp__date=date.today()
    ).count()
    
    if failover_events_today > 0:
        report += f"- Failover events today: {failover_events_today} ⚠️\n"
    
    # Security events today
    security_events = ActivityLog.objects.filter(
        router=router,
        activity_type='security_ban',
        timestamp__date=date.today()
    ).count()
    
    if security_events > 0:
        report += f"- Security events today: {security_events} 🛡️\n"
    
    report += "\n"
except Exception as e:
    report += "⚙️ *System Health*: Database error.\n\n"
    print(f"Error analyzing health: {e}")

# Summary
report += "Semua sistem berjalan normal! ✨"

print(report)
print("\nSending Daily Report via Telegram...")

try:
    send_telegram(report)
    print("Daily Report sent successfully.")
except Exception as e:
    print(f"Failed to send report: {e}")
