import base64

import requests
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from scouting.models import Event, Match, TbaApiKey, Team


class Command(BaseCommand):
    help = "Update teams and matches from The Blue Alliance API (including team logos)"

    def _get_json(self, url, headers):
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()

    def _fetch_team_logo_bytes(self, headers, team_number, game_year):
        media_url = f"https://www.thebluealliance.com/api/v3/team/frc{team_number}/media/{game_year}"
        media_items = self._get_json(media_url, headers)

        # Prefer team avatar images; TBA provides avatar image bytes as base64.
        for item in media_items:
            if item.get("type") != "avatar":
                continue
            details = item.get("details") or {}
            b64_image = details.get("base64Image")
            if not b64_image:
                continue
            try:
                return base64.b64decode(b64_image), ".png"
            except Exception:
                continue

        return None, None

    def handle(self, *args, **options):
        try:
            api_key = TbaApiKey.objects.get(active=True).api_key
        except ObjectDoesNotExist:
            self.stdout.write("Active API key not found.")
            return

        active_event = Event.objects.get(active=True)
        event_key = active_event.tba_event_key
        headers = {"X-TBA-Auth-Key": api_key}

        teams_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams/simple"
        teams = self._get_json(teams_url, headers)

        logos_saved = 0
        for team in teams:
            team_number = team["team_number"]
            team_obj, _ = Team.objects.update_or_create(
                team_number=team_number,
                defaults={"team_name": team.get("nickname") or f"Team {team_number}"},
            )

            active_event.teams.add(team_obj)

            logo_bytes, ext = self._fetch_team_logo_bytes(headers, team_number, active_event.game.year)
            if not logo_bytes:
                continue

            file_name = f"frc{team_number}_logo{ext}"
            team_obj.team_logo.save(file_name, ContentFile(logo_bytes), save=True)
            logos_saved += 1

        active_event.save()

        matches_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/matches/simple"
        matches = self._get_json(matches_url, headers)

        for match in matches:
            if match["comp_level"] != "qm":
                continue

            Match.objects.update_or_create(
                match_number=match["match_number"],
                event_id=active_event,
                defaults={
                    "team_red_1": Team.objects.get_or_create(
                        team_number=match["alliances"]["red"]["team_keys"][0][3:]
                        if match["alliances"]["red"]["team_keys"][0]
                        else 9999
                    )[0],
                    "team_red_2": Team.objects.get_or_create(
                        team_number=match["alliances"]["red"]["team_keys"][1][3:]
                        if match["alliances"]["red"]["team_keys"][1]
                        else 9999
                    )[0],
                    "team_red_3": Team.objects.get_or_create(
                        team_number=match["alliances"]["red"]["team_keys"][2][3:]
                        if match["alliances"]["red"]["team_keys"][2]
                        else 9999
                    )[0],
                    "team_blue_1": Team.objects.get_or_create(
                        team_number=match["alliances"]["blue"]["team_keys"][0][3:]
                        if match["alliances"]["blue"]["team_keys"][0]
                        else 9999
                    )[0],
                    "team_blue_2": Team.objects.get_or_create(
                        team_number=match["alliances"]["blue"]["team_keys"][1][3:]
                        if match["alliances"]["blue"]["team_keys"][1]
                        else 9999
                    )[0],
                    "team_blue_3": Team.objects.get_or_create(
                        team_number=match["alliances"]["blue"]["team_keys"][2][3:]
                        if match["alliances"]["blue"]["team_keys"][2]
                        else 9999
                    )[0],
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Teams, matches, and logos updated successfully. Logos saved: {logos_saved}"
            )
        )
