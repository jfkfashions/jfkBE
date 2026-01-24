from django.core.management.base import BaseCommand
from django.db.models import Count
from biobio.models import Measurement


class Command(BaseCommand):
    help = "Remove duplicate measurement records, keeping only the most recent one for each username"

    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.WARNING("Starting cleanup of duplicate measurements...")
        )

        # Find all usernames that have duplicates
        duplicates = (
            Measurement.objects.values("username")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        total_deleted = 0

        for item in duplicates:
            username = item["username"]
            count = item["count"]

            # Get all measurements for this username, ordered by id (oldest first)
            measurements = list(
                Measurement.objects.filter(username=username).order_by("id")
            )

            # Keep the most recent one (last in the list) and delete the rest
            to_delete = measurements[:-1] if len(measurements) > 1 else []
            deleted_count = len(to_delete)

            if deleted_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'Found {count} measurements for username "{username}". '
                        f"Keeping the most recent one, deleting {deleted_count} duplicates."
                    )
                )

                for measurement in to_delete:
                    measurement.delete()
                    total_deleted += 1

        if total_deleted > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully deleted {total_deleted} duplicate measurement(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✓ No duplicate measurements found. Database is clean."
                )
            )
