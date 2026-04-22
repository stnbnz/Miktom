import os
import subprocess
import sys
from datetime import timedelta

from django.core.management import BaseCommand, call_command
from django.db import transaction
from django.utils import timezone

from dashboard.models import (
    ActiveUser,
    ActivityLog,
    AutomationRunLog,
    InterfaceMetrics,
    Router,
    SystemAlert,
    SystemMetrics,
)


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))


class Command(BaseCommand):
    help = "Run scheduled maintenance and monitoring tasks for cron."

    def add_arguments(self, parser):
        parser.add_argument("--router-id", type=int, help="Run only for one router id")
        parser.add_argument(
            "--run-scripts",
            action="store_true",
            help="Execute standalone automation scripts in project root",
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=14,
            help="Retention for high-volume monitoring tables (default 14)",
        )

    def handle(self, *args, **options):
        router_id = options.get("router_id")
        retention_days = max(1, options.get("retention_days") or 14)
        run_scripts = options.get("run_scripts", False)

        routers = Router.objects.all()
        if router_id:
            routers = routers.filter(id=router_id)

        if not routers.exists():
            self.stdout.write(self.style.WARNING("No routers configured."))
            return

        run_log = AutomationRunLog.objects.create(
            task_name="run_automation",
            status="RUNNING",
            metadata={
                "router_id": router_id,
                "retention_days": retention_days,
                "run_scripts": run_scripts,
            },
        )

        summary_lines = []
        script_results = []
        ok = True

        try:
            call_command("expire_vouchers", router_id=router_id)
            summary_lines.append("expire_vouchers: done")

            cleanup_stats = self._cleanup_old_data(retention_days)
            summary_lines.append(
                "cleanup: "
                + ", ".join(f"{key}={val}" for key, val in cleanup_stats.items())
            )

            if run_scripts:
                script_results = self._run_standalone_scripts()
                summary_lines.append(
                    "scripts: " + ", ".join(f"{x['name']}={x['status']}" for x in script_results)
                )

            for router in routers:
                ActivityLog.objects.create(
                    router=router,
                    user="cron",
                    activity_type="backup_auto",
                    description="Scheduled automation run completed.",
                    metadata={
                        "retention_days": retention_days,
                        "run_scripts": run_scripts,
                        "script_results": script_results,
                    },
                    success=True,
                )
        except Exception as exc:
            ok = False
            summary_lines.append(f"error: {exc}")
            self.stderr.write(self.style.ERROR(f"Automation failed: {exc}"))
        finally:
            run_log.finished_at = timezone.now()
            run_log.status = "SUCCESS" if ok else "FAILED"
            run_log.summary = "\n".join(summary_lines)
            run_log.metadata = {
                **run_log.metadata,
                "script_results": script_results,
            }
            run_log.save(update_fields=["finished_at", "status", "summary", "metadata"])

        if ok:
            self.stdout.write(self.style.SUCCESS("Automation pipeline completed."))
        else:
            raise SystemExit(1)

    @transaction.atomic
    def _cleanup_old_data(self, retention_days):
        cutoff = timezone.now() - timedelta(days=retention_days)
        return {
            "system_metrics": SystemMetrics.objects.filter(timestamp__lt=cutoff).delete()[0],
            "interface_metrics": InterfaceMetrics.objects.filter(timestamp__lt=cutoff).delete()[0],
            "active_users": ActiveUser.objects.filter(timestamp__lt=cutoff, is_active=False).delete()[0],
            "system_alerts": SystemAlert.objects.filter(timestamp__lt=cutoff, resolved=True).delete()[0],
            "activity_logs": ActivityLog.objects.filter(timestamp__lt=cutoff).delete()[0],
        }

    def _run_standalone_scripts(self):
        script_names = [
            "monitor-router.py",
            "device-tracker.py",
            "security-shield.py",
            "smart-qos.py",
            "failover-wan.py",
            "speedtest-logger.py",
            "daily-report.py",
        ]
        results = []
        for script_name in script_names:
            script_path = os.path.join(ROOT_DIR, script_name)
            if not os.path.exists(script_path):
                results.append({"name": script_name, "status": "SKIPPED", "detail": "not found"})
                continue

            proc = subprocess.run(
                [sys.executable, script_path],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
            )
            status = "SUCCESS" if proc.returncode == 0 else "FAILED"
            detail = (proc.stdout or proc.stderr or "").strip()[:800]
            results.append({"name": script_name, "status": status, "detail": detail})
        return results
