# scouting/management/commands/allianceselection.py

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from scouting.models import Event, TbaApiKey, Alliance
import tbapy


class Command(BaseCommand):
    help = "Sync alliance data from TBA and store only the specified fields in the Alliance model."

    def handle(self, *args, **options):
        # 1. Get the active TBA API key
        try:
            api_key = TbaApiKey.objects.get(active=True).api_key
        except ObjectDoesNotExist:
            self.stdout.write(self.style.ERROR("Active API key not found."))
            return

        tba = tbapy.TBA(api_key)

        # 2. Find the active event
        try:
            event = Event.objects.get(active=True)
        except Event.DoesNotExist:
            self.stdout.write(self.style.ERROR("No active event found."))
            return

        # 3. Fetch alliance data from TBA
        alliances_data = tba.event_alliances(event.tba_event_key)
        if not alliances_data:
            self.stdout.write(self.style.ERROR("No alliance data available from TBA."))
            return

        for alliance in alliances_data:
            # Basic fields
            name = alliance.get("name")
            declines = alliance.get("declines", [])
            picks = alliance.get("picks", [])

            # Remove 'frc' prefix
            picks_no_frc = [p[3:] for p in picks if p.startswith("frc")]
            declines_no_frc = [d[3:] for d in declines if d.startswith("frc")]

            # The main status object
            status_data = alliance.get("status", {})
            alliance_status = status_data.get("status", "")
            alliance_playoff_avg = status_data.get("playoff_average", 0.0)

            # The backup object
            backup_data = alliance.get("backup", {})
            backup_in = backup_data.get("_in", "")
            backup_out = backup_data.get("out", "")

            # Remove 'frc' prefix for backup
            if backup_in.startswith("frc"):
                backup_in = backup_in[3:]
            if backup_out.startswith("frc"):
                backup_out = backup_out[3:]

            backup_status = backup_data.get("status", "")
            backup_playoff_avg = backup_data.get("playoff_average", 0.0)

            # Create or update the Alliance object
            alliance_obj, created = Alliance.objects.update_or_create(
                event=event,
                picks=picks_no_frc,  # used for the unique constraint
                defaults={
                    "name": name,
                    "declines": declines_no_frc,
                    "status": alliance_status,
                    "playoff_average": alliance_playoff_avg,
                    "backup_in": backup_in,
                    "backup_out": backup_out,
                    "backup_status": backup_status,
                    "backup_playoff_average": backup_playoff_avg,
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"Created alliance: {name or 'Unknown'} with picks {picks_no_frc}"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated alliance: {name or 'Unknown'} with picks {picks_no_frc}"
                ))

        self.stdout.write(self.style.SUCCESS("Alliance data sync completed."))
