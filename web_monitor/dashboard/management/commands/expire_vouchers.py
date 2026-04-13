import routeros_api
from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import Router, Voucher

class Command(BaseCommand):
    help = 'Sync voucher usage from MikroTik and suspend expired hotspot users.'

    def add_arguments(self, parser):
        parser.add_argument('--router-id', type=int, help='Router ID to use for syncing vouchers')

    def handle(self, *args, **options):
        router_id = options.get('router_id')
        routers = Router.objects.all()
        if router_id:
            routers = routers.filter(id=router_id)

        if not routers.exists():
            self.stdout.write(self.style.WARNING('No routers configured.'))
            return

        for router in routers:
            self.stdout.write(f"Processing router {router.name} ({router.ip_address})")
            try:
                connection = routeros_api.RouterOsApiPool(
                    router.ip_address,
                    username=router.username,
                    password=router.password,
                    port=router.port,
                    plaintext_login=True,
                )
                api = connection.get_api()
                active_resource = api.get_resource('/ip/hotspot/active')
                hotspot_user = api.get_resource('/ip/hotspot/user')

                active_sessions = active_resource.get()
                active_by_code = {s.get('user', ''): s for s in active_sessions}

                # Mark vouchers as used when a matching active session exists
                for code, session in active_by_code.items():
                    try:
                        voucher = Voucher.objects.get(code=code)
                    except Voucher.DoesNotExist:
                        continue

                    if not voucher.is_used:
                        voucher.mark_used()
                        self.stdout.write(self.style.SUCCESS(f"Marked voucher {code} as used"))

                # Suspend expired vouchers in MikroTik
                now = timezone.now()
                expired_vouchers = Voucher.objects.filter(expires_at__lte=now)
                for voucher in expired_vouchers:
                    try:
                        users = hotspot_user.get(name=voucher.code)
                        if users:
                            user_id = users[0]['.id']
                            hotspot_user.set(id=user_id, disabled='yes')
                            self.stdout.write(self.style.SUCCESS(f"Disabled hotspot user {voucher.code}"))

                        session = active_by_code.get(voucher.code)
                        if session:
                            active_resource.remove(id=session['.id'])
                            self.stdout.write(self.style.SUCCESS(f"Removed active session {voucher.code}"))
                    except Exception as exc:
                        self.stderr.write(f"Failed to suspend {voucher.code}: {exc}")

            except Exception as exc:
                self.stderr.write(f"Router {router.ip_address} failure: {exc}")
            finally:
                try:
                    connection.disconnect()
                except Exception:
                    pass
