import sys
import os
import django
import requests
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import (
    SpeedtestLog, TrackedDevice, FailoverState, ActivityLog,
    SystemMetrics, FailoverEvent, Router, VoucherUsage
)
from django.db.models import Avg, Count, Max, Min
from django.utils import timezone

try:
    from alert import send_telegram_markdown
except ImportError:
    def send_telegram_markdown(msg): print("[alert] Not available:", msg)


def generate_and_send_report():
    print("==================================")
    print(" MikroTik Daily Network Reporter")
    print(f" Time: {datetime.now()}")
    print("==================================")

    routers = Router.objects.filter(is_active=True)
    if not routers.exists():
        routers = Router.objects.all()
        if not routers.exists():
            print("Error: No routers found in database.")
            return

    today = timezone.now().date()

    for router in routers:
        print(f"\n--- Generating report for: {router.name} ---")
        report = f"📊 *DAILY NETWORK REPORT*\n"
        report += f"📅 `{today}`  |  🖧 `{router.name}` ({router.ip_address})\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 1. System Health (latest snapshot)
        try:
            latest = SystemMetrics.objects.filter(router=router).order_by('-timestamp').first()
            if latest:
                report += "⚙️ *System Health (Latest)*\n"
                report += f"• CPU: `{latest.cpu_load}%`\n"
                report += f"• RAM: `{latest.ram_usage}%`\n"
                report += f"• Internet: `{latest.internet_status}`\n"
                report += f"• Active Users: `{latest.active_users}`\n"
                report += f"• Banned IPs: `{latest.banned_ips}`\n\n"
            else:
                report += "⚙️ *System Health*: No data today.\n\n"
        except Exception as e:
            report += "⚙️ *System Health*: Error reading data.\n\n"
            print(f"  Error [health]: {e}")

        # 2. Connected Devices
        try:
            total_devices = TrackedDevice.objects.filter(router=router).count()
            online_now = TrackedDevice.objects.filter(router=router, is_online=True).count()
            new_today = TrackedDevice.objects.filter(router=router, first_seen__date=today).count()

            report += "📱 *Devices*\n"
            report += f"• Total Tracked: `{total_devices}`\n"
            report += f"• Online Now: `{online_now}`\n"
            report += f"• New Today: `{new_today}`\n\n"
        except Exception as e:
            report += "📱 *Devices*: Error reading data.\n\n"
            print(f"  Error [devices]: {e}")

        # 3. Internet Speed (daily average)
        try:
            speeds = SpeedtestLog.objects.filter(
                router=router, test_time__date=today
            ).aggregate(
                avg_dl=Avg('download'),
                avg_ul=Avg('upload'),
                avg_ping=Avg('ping'),
                tests=Count('id'),
                min_dl=Min('download'),
                max_dl=Max('download'),
            )

            if speeds['tests'] and speeds['tests'] > 0:
                report += f"🌐 *Internet Speed ({speeds['tests']} tests)*\n"
                report += f"• Avg Download: `{speeds['avg_dl']:.2f} Mbps`\n"
                report += f"• Avg Upload: `{speeds['avg_ul']:.2f} Mbps`\n"
                report += f"• Min/Max DL: `{speeds['min_dl']:.2f}` / `{speeds['max_dl']:.2f} Mbps`\n"
                report += f"• Avg Latency: `{speeds['avg_ping']:.2f} ms`\n\n"
            else:
                report += "🌐 *Internet Speed*: No speedtests run today.\n\n"
        except Exception as e:
            report += "🌐 *Internet Speed*: Error reading data.\n\n"
            print(f"  Error [speed]: {e}")

        # 4. WAN Failover
        try:
            failover_state = FailoverState.objects.filter(router=router).first()
            events_today = FailoverEvent.objects.filter(router=router, timestamp__date=today).count()

            report += "🔄 *WAN Failover*\n"
            if failover_state:
                wan_label = "ISP1 (Primary) ✅" if failover_state.active_wan == 'ISP1_ACTIVE' else "ISP2 (Backup) ⚠️"
                report += f"• Active WAN: `{wan_label}`\n"
            report += f"• Failover Events Today: `{events_today}`\n\n"
        except Exception as e:
            report += "🔄 *WAN Failover*: Error reading data.\n\n"
            print(f"  Error [failover]: {e}")

        # 5. Security Events
        try:
            security_bans = ActivityLog.objects.filter(
                router=router, activity_type='security_ban', timestamp__date=today
            ).count()

            report += "🛡️ *Security*\n"
            if security_bans > 0:
                report += f"• IPs Banned Today: `{security_bans}` ⚠️\n\n"
            else:
                report += "• No security incidents today ✅\n\n"
        except Exception as e:
            report += "🛡️ *Security*: Error reading data.\n\n"
            print(f"  Error [security]: {e}")

        # 6. Vouchers
        try:
            vouchers_used = VoucherUsage.objects.filter(
                router=router, action='used', timestamp__date=today
            ).count()
            vouchers_gen = ActivityLog.objects.filter(
                router=router, activity_type='voucher_generate', timestamp__date=today
            ).count()

            report += "🎫 *Vouchers*\n"
            report += f"• Generated Today: `{vouchers_gen}`\n"
            report += f"• Used Today: `{vouchers_used}`\n\n"
        except Exception as e:
            report += "🎫 *Vouchers*: Error reading data.\n\n"
            print(f"  Error [vouchers]: {e}")

        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "✨ *Laporan harian selesai!*"

        print(f"\n{report}\n")
        print(f"Sending report for {router.name} via Telegram...")

        try:
            send_telegram_markdown(report)
            print("Report sent successfully!\n")
        except Exception as e:
            print(f"Failed to send Telegram: {e}\n")


if __name__ == '__main__':
    generate_and_send_report()
