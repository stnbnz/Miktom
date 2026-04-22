from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Drop all data and rebuild database schema from migrations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes-i-know",
            action="store_true",
            help="Required confirmation flag to run destructive rebuild.",
        )

    def handle(self, *args, **options):
        if not options.get("yes_i_know"):
            self.stdout.write(
                self.style.WARNING(
                    "Cancelled. Add --yes-i-know to rebuild database."
                )
            )
            return

        self.stdout.write(self.style.WARNING("Flushing all data..."))
        call_command("flush", interactive=False)

        self.stdout.write("Applying all migrations...")
        call_command("migrate", interactive=False)

        self.stdout.write(self.style.SUCCESS("Database rebuild completed."))
