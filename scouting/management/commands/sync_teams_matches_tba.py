import base64

import requests
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from scouting.models import Event, Match, MatchResult, NexusApiKey, PitScoutData, TbaApiKey, Team


class Command(BaseCommand):
    help = (
        "Update teams and matches from The Blue Alliance API "
        "(including team logos, pit locations, and FRC Nexus links when available)"
    )

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

    def _extract_pit_location(self, team_payload, status_payload):
        # TBA payloads are not consistent for this; try several likely keys.
        for payload in [status_payload or {}, team_payload or {}]:
            for key in ("pit_location", "pitLocation", "pit", "pit_number", "pitNumber"):
                value = payload.get(key)
                if value:
                    return str(value).strip()
        return ""

    def _build_frc_nexus_map_url(self, event_key, team_number):
        return f"https://frc.nexus/en/event/{event_key}/team/{team_number}/map"

    def _to_int_or_none(self, value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _to_float_or_none(self, value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_alliance_rp(self, score_breakdown, alliance):
        if not isinstance(score_breakdown, dict):
            return None
        alliance_data = score_breakdown.get(alliance)
        if not isinstance(alliance_data, dict):
            return None

        # Preferred direct keys when available.
        for key in ("rp", "ranking_points", "rankingPoints", "total_rp"):
            value = self._to_float_or_none(alliance_data.get(key))
            if value is not None:
                return value

        # Fallback: sum game-specific ranking point booleans/numerics.
        rp_total = 0.0
        found_any = False
        for key, raw_value in alliance_data.items():
            key_lower = str(key).lower()
            if "rankingpoint" in key_lower or key_lower.endswith("_rp"):
                if isinstance(raw_value, bool):
                    rp_total += 1.0 if raw_value else 0.0
                    found_any = True
                else:
                    numeric = self._to_float_or_none(raw_value)
                    if numeric is not None:
                        rp_total += numeric
                        found_any = True

        return rp_total if found_any else None

    def _fetch_nexus_pits_map(self, event_key, nexus_api_key):
        """
        Returns {team_number: pit_location} from FRC Nexus, if configured/available.
        """
        url = f"https://frc.nexus/api/v1/event/{event_key}/pits"
        headers = {"Nexus-Api-Key": nexus_api_key}

        try:
            data = requests.get(url, headers=headers, timeout=20).json()
        except requests.RequestException:
            return {}
        except ValueError:
            return {}

        if not isinstance(data, dict):
            return {}

        pits = {}
        for team_number, pit_location in data.items():
            try:
                team_int = int(team_number)
            except (TypeError, ValueError):
                continue
            pits[team_int] = str(pit_location).strip()
        return pits

    def handle(self, *args, **options):
        try:
            tba_api_key = TbaApiKey.objects.get(active=True).api_key
        except ObjectDoesNotExist:
            self.stdout.write("Active TBA API key not found.")
            return

        try:
            nexus_api_key = NexusApiKey.objects.get(active=True).api_key
        except ObjectDoesNotExist:
            self.stdout.write("Active FRC Nexus API key not found.")
            return

        active_event = Event.objects.get(active=True)
        event_key = active_event.tba_event_key
        headers = {"X-TBA-Auth-Key": tba_api_key}

        teams_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams"
        teams = self._get_json(teams_url, headers)
        team_statuses_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams/statuses"
        team_statuses = self._get_json(team_statuses_url, headers)
        nexus_pits_map = self._fetch_nexus_pits_map(event_key, nexus_api_key)

        logos_saved = 0
        pits_saved = 0
        for team in teams:
            team_number = team["team_number"]
            team_key = f"frc{team_number}"
            team_obj, _ = Team.objects.update_or_create(
                team_number=team_number,
                defaults={"team_name": team.get("nickname") or f"Team {team_number}"},
            )

            active_event.teams.add(team_obj)

            logo_bytes, ext = self._fetch_team_logo_bytes(headers, team_number, active_event.game.year)
            if logo_bytes:
                file_name = f"frc{team_number}_logo{ext}"
                team_obj.team_logo.save(file_name, ContentFile(logo_bytes), save=True)
                logos_saved += 1

            pit_location = nexus_pits_map.get(team_number) or self._extract_pit_location(team, team_statuses.get(team_key))
            frc_nexus_url = self._build_frc_nexus_map_url(event_key, team_number)
            pit_data, _ = PitScoutData.objects.get_or_create(team=team_obj, event=active_event)
            pit_data.pit_location = pit_location or pit_data.pit_location
            pit_data.frc_nexus_url = frc_nexus_url
            pit_data.save(update_fields=["pit_location", "frc_nexus_url"])
            if pit_location:
                pits_saved += 1

        active_event.save()

        matches_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/matches"
        matches = self._get_json(matches_url, headers)

        for match in matches:
            if match["comp_level"] != "qm":
                continue

            match_obj, _ = Match.objects.update_or_create(
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

            red_score = self._to_int_or_none((match.get("alliances") or {}).get("red", {}).get("score"))
            blue_score = self._to_int_or_none((match.get("alliances") or {}).get("blue", {}).get("score"))
            red_rp = self._extract_alliance_rp(match.get("score_breakdown"), "red")
            blue_rp = self._extract_alliance_rp(match.get("score_breakdown"), "blue")
            is_final = (
                match.get("actual_time") is not None
                or (red_score is not None and blue_score is not None and red_score >= 0 and blue_score >= 0)
            )

            MatchResult.objects.update_or_create(
                match=match_obj,
                defaults={
                    "red_score": red_score if is_final else None,
                    "blue_score": blue_score if is_final else None,
                    "red_rp": red_rp if is_final else None,
                    "blue_rp": blue_rp if is_final else None,
                    "is_final": is_final,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Teams, matches, logos, and pit metadata updated successfully. "
                f"Logos saved: {logos_saved}, pit locations saved: {pits_saved}"
            )
        )
