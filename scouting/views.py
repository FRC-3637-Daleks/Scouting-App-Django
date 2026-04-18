from .forms import *
from django.shortcuts import redirect
from django.forms.models import model_to_dict
from django.core import serializers
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Team, Event, PitScoutData, LivestreamRecording
from .forms import PitScoutDataForm
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.core.management import call_command
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
import json
import time
import os
import subprocess
from django.shortcuts import render
from .models import (
    TeamRanking,
    Match,
    MatchResult,
    NexusApiKey,
    PlayoffMatch,
    PitDashboardLiveStatus,
)
from .recording_service import get_active_recording, start_recording, stop_recording
from .recording_service import open_recording_or_folder, get_recording_source_preflight
from django.db.models import F
from django.db.models import OuterRef, Subquery, Value, FloatField, IntegerField
from pathlib import Path
from PIL import Image
import requests
from requests.adapters import HTTPAdapter
import re
import ipaddress
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo
from statistics import median
from urllib3.util.retry import Retry
from django.views.decorators.http import require_POST
from scouting.ntTablesGetter import get_status

#Enabled = "e", disabled = "d", not connected = "n"
def _get_NT_tables():
    try:
        nt_status = get_status()
    except Exception:
        return "n"

    if nt_status == "ENABLED":
        return "e"
    if nt_status == "DISABLED":
        return "d"
    return "n"


def _get_robot_status_payload_from_nt():
    status_code = _get_NT_tables()
    label_map = {
        "e": "Robot Enabled",
        "d": "Robot Disabled",
        "n": "Robot Disconnected",
    }
    return {
        "status_code": status_code,
        "label": label_map.get(status_code, "Robot Disconnected"),
    }


def _recording_file_exists(recording_obj):
    rel_path = str(getattr(recording_obj, "output_file", "") or "").strip().replace("\\", "/")
    if not rel_path:
        return False
    abs_path = Path(settings.MEDIA_ROOT) / rel_path
    return abs_path.is_file()


def _normalize_live_field(value, default="?"):
    text = str(value).strip() if value is not None else ""
    return text if text else default


def _parse_match_clock_to_seconds(clock_text):
    match = re.match(r"^(\d{1,2}):([0-5]\d)$", str(clock_text or "").strip())
    if not match:
        return None
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    return (minutes * 60) + seconds


def _extract_first_int(value):
    match = re.search(r"(\d+)", str(value or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _looks_like_no_match_sample(match_label, game_time, blue_score, red_score):
    match_text = str(match_label or "").strip().lower()
    time_text = str(game_time or "").strip()
    blue_text = str(blue_score or "").strip()
    red_text = str(red_score or "").strip()

    no_match_labels = {"", "0", "00", "?", "q0"}
    default_times = {"0:20", "00:20", "0:00", "00:00", "?"}
    default_scores = {"0", "00", "?"}

    return (
        match_text in no_match_labels
        and time_text in default_times
        and blue_text in default_scores
        and red_text in default_scores
    )


def _is_valid_score_text(value):
    text = str(value or "").strip()
    if not text or text == "?":
        return False
    if not re.fullmatch(r"\d{1,3}", text):
        return False
    try:
        parsed = int(text)
    except (TypeError, ValueError):
        return False
    return 0 <= parsed <= 999


def _looks_like_garbage_live_sample(match_label, game_time, blue_score, red_score):
    match_text = str(match_label or "").strip()
    time_text = str(game_time or "").strip()
    blue_text = str(blue_score or "").strip()
    red_text = str(red_score or "").strip()

    if "?" in {match_text, time_text, blue_text, red_text}:
        return True

    if not _is_valid_score_text(blue_text) or not _is_valid_score_text(red_text):
        return True

    # Reject absurd OCR outputs (e.g. 1000+, mixed chars already rejected above).
    if int(blue_text) >= 1000 or int(red_text) >= 1000:
        return True

    match_num = _extract_first_int(match_text)
    if match_num is None:
        return True
    if match_num < 0 or match_num > 300:
        return True

    clock_seconds = _parse_match_clock_to_seconds(time_text)
    if clock_seconds is None:
        return True
    if clock_seconds > 150:
        return True

    return False


def _is_intermediate_period_sample(previous_status, match_label, game_time, blue_score, red_score):
    if _looks_like_no_match_sample(match_label, game_time, blue_score, red_score):
        return True
    if _looks_like_garbage_live_sample(match_label, game_time, blue_score, red_score):
        return True

    time_text = str(game_time or "").strip()
    is_020 = time_text in {"0:20", "00:20"}
    if not is_020:
        return False

    if previous_status and previous_status.match_started is False:
        return True

    if not previous_status:
        return False

    prev_time = str(previous_status.game_time or "").strip()
    prev_blue = _normalize_live_field(previous_status.blue_score)
    prev_red = _normalize_live_field(previous_status.red_score)
    prev_match = str(previous_status.match_label or "").strip()
    new_match = str(match_label or "").strip()

    return (
        prev_time in {"0:20", "00:20"}
        and prev_blue == _normalize_live_field(blue_score)
        and prev_red == _normalize_live_field(red_score)
        and (not prev_match or prev_match == new_match)
    )


def _normalize_label_for_compare(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _infer_match_started(previous_status, new_match, new_time, new_blue_score, new_red_score):
    if not previous_status:
        return None

    previous_match = (previous_status.match_label or "").strip()
    previous_time = (previous_status.game_time or "").strip()
    previous_blue_score = _normalize_live_field(previous_status.blue_score)
    previous_red_score = _normalize_live_field(previous_status.red_score)

    if not previous_match or previous_match != new_match:
        return None

    # If game clock and scores are unchanged from the last sample, treat as "not started yet".
    if (
        previous_time
        and previous_time == new_time
        and previous_blue_score == new_blue_score
        and previous_red_score == new_red_score
    ):
        return False

    previous_seconds = _parse_match_clock_to_seconds(previous_time)
    new_seconds = _parse_match_clock_to_seconds(new_time)
    if previous_seconds is not None and new_seconds is not None and new_seconds < previous_seconds:
        return True

    if previous_blue_score != new_blue_score or previous_red_score != new_red_score:
        return True

    return previous_status.match_started


def _is_localhost_or_local_ip(request):
    host = (request.get_host() or "").strip()
    if host.startswith("[") and "]" in host:
        host = host[1:].split("]", 1)[0]
    elif ":" in host:
        host = host.split(":", 1)[0]

    if host.lower() in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        ip_value = ipaddress.ip_address(host)
        return bool(ip_value.is_private or ip_value.is_loopback)
    except ValueError:
        return False

def _get_standscout_compressed_url(image_field, max_width=900, quality=65):
    """
    Build and cache a compressed JPEG copy for stand scout screens.
    Returns a media URL or None when source image does not exist.
    """
    if not image_field:
        return None

    try:
        source_path = Path(image_field.path)
    except Exception:
        return None

    if not source_path.exists():
        return None

    cache_dir = Path(settings.MEDIA_ROOT) / "cache" / "standscout"
    cache_dir.mkdir(parents=True, exist_ok=True)

    stamp = int(source_path.stat().st_mtime)
    cache_name = f"{source_path.stem}_{stamp}.jpg"
    cache_path = cache_dir / cache_name

    if not cache_path.exists():
        with Image.open(source_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
            img.save(cache_path, format="JPEG", quality=quality, optimize=True, progressive=True)

    return f"{settings.MEDIA_URL}cache/standscout/{cache_name}"


def _normalize_probability(value):
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None

    # Support either 0-1 or 0-100 formats.
    if probability > 1:
        probability = probability / 100.0

    return max(0.0, min(1.0, probability))


def _get_team_alliance(match_obj, team_number):
    red_teams = (
        match_obj.team_red_1.team_number,
        match_obj.team_red_2.team_number,
        match_obj.team_red_3.team_number,
    )
    blue_teams = (
        match_obj.team_blue_1.team_number,
        match_obj.team_blue_2.team_number,
        match_obj.team_blue_3.team_number,
    )

    if team_number in red_teams:
        return "red"
    if team_number in blue_teams:
        return "blue"
    return None


def _extract_alliance_win_probability(match_payload, alliance):
    """
    Extract a specific alliance win probability from Statbotics REST payload.
    Handles both top-level and nested prediction layouts.
    """
    if not isinstance(match_payload, dict) or alliance not in {"red", "blue"}:
        return None

    alliance_key = f"{alliance}_win_prob"
    opposite_alliance = "blue" if alliance == "red" else "red"
    opposite_key = f"{opposite_alliance}_win_prob"

    for key in (alliance_key, f"{alliance}WinProb"):
        if key in match_payload:
            normalized = _normalize_probability(match_payload.get(key))
            if normalized is not None:
                return normalized

    # Common REST shape may include only one side's win probability.
    for key in (opposite_key, f"{opposite_alliance}WinProb"):
        if key in match_payload:
            normalized = _normalize_probability(match_payload.get(key))
            if normalized is not None:
                return 1.0 - normalized

    for container_name in ("pred", "epa"):
        container = match_payload.get(container_name)
        if isinstance(container, dict):
            for key in (alliance_key, f"{alliance}WinProb"):
                if key in container:
                    normalized = _normalize_probability(container.get(key))
                    if normalized is not None:
                        return normalized
            for key in (opposite_key, f"{opposite_alliance}WinProb"):
                if key in container:
                    normalized = _normalize_probability(container.get(key))
                    if normalized is not None:
                        return 1.0 - normalized

    # Some payloads return winner + winner probability instead of alliance-specific keys.
    winner = match_payload.get("epa_winner") or match_payload.get("pred_winner")
    winner_prob = match_payload.get("epa_win_prob")
    if winner_prob is None:
        winner_prob = match_payload.get("pred_win_prob")
    if winner_prob is None and isinstance(match_payload.get("epa"), dict):
        winner_prob = match_payload["epa"].get("win_prob")
    if winner_prob is None and isinstance(match_payload.get("pred"), dict):
        winner_prob = match_payload["pred"].get("win_prob")

    normalized = _normalize_probability(winner_prob)
    if normalized is None or winner not in {"red", "blue"}:
        return None

    return normalized if winner == alliance else 1.0 - normalized


def _extract_team_perspective_win_probability(match_payload):
    """
    Extract team-perspective win probability when a team-filtered endpoint provides it.
    """
    if not isinstance(match_payload, dict):
        return None

    for key in ("win_prob", "winProb", "epa_win_prob", "pred_win_prob"):
        if key in match_payload:
            normalized = _normalize_probability(match_payload.get(key))
            if normalized is not None:
                return normalized

    for container_name in ("epa", "pred"):
        container = match_payload.get(container_name)
        if isinstance(container, dict):
            for key in ("win_prob", "winProb"):
                if key in container:
                    normalized = _normalize_probability(container.get(key))
                    if normalized is not None:
                        return normalized
    return None


def _parse_match_number_from_payload(payload_row):
    if not isinstance(payload_row, dict):
        return None

    raw_number = payload_row.get("match_number")
    try:
        if raw_number is not None:
            return int(raw_number)
    except (TypeError, ValueError):
        pass

    for key_name in ("key", "match", "match_key"):
        value = payload_row.get(key_name)
        if isinstance(value, str):
            parsed = re.search(r"_qm(\d+)$", value)
            if parsed:
                return int(parsed.group(1))
    return None


def _extract_qual_match_number(label, payload_row=None):
    label_text = str(label or "")
    label_patterns = (
        r"^Qualification\s+(\d+)\b",
        r"^Qual(?:ification)?\s*#?\s*(\d+)\b",
        r"^QM\s*#?\s*(\d+)\b",
    )
    for pattern in label_patterns:
        parsed = re.search(pattern, label_text, flags=re.IGNORECASE)
        if parsed:
            return int(parsed.group(1))

    return _parse_match_number_from_payload(payload_row)


def _parse_nexus_dashboard_payload(nexus_status, display_tz):
    matches_payload = nexus_status.get("matches")
    if not isinstance(matches_payload, list):
        matches_payload = []

    now_queuing = nexus_status.get("nowQueuing") or nexus_status.get("now_queuing")
    announcements = nexus_status.get("announcements") or []
    announcements_display = _format_announcements(announcements, display_tz)
    parts_requests = nexus_status.get("partsRequests") or []
    parts_requests_display = _format_parts_requests(parts_requests, display_tz)
    current_match = nexus_status.get("currentMatch") or nexus_status.get("current_match")
    if not current_match:
        current_match, _ = _derive_current_match_from_matches(matches_payload)

    current_qual_match_num = None
    if not now_queuing:
        derived_label, derived_match_num = _derive_now_queuing_from_matches(matches_payload)
        if derived_label:
            now_queuing = derived_label
            current_qual_match_num = derived_match_num

    if isinstance(now_queuing, str):
        match = re.search(r"Qualification\s+(\d+)", now_queuing, flags=re.IGNORECASE)
        if match:
            current_qual_match_num = int(match.group(1))

    queueing_match_numbers = set()
    queue_time_by_match = {}
    queue_eta_epoch_by_match = {}
    start_eta_epoch_by_match = {}
    queue_status_by_match = {}

    for nexus_match in matches_payload:
        if not isinstance(nexus_match, dict):
            continue
        label = nexus_match.get("label") or ""
        match = re.search(r"^Qualification\s+(\d+)", label, flags=re.IGNORECASE)
        if not match:
            continue

        match_number = int(match.group(1))
        status_text = str(nexus_match.get("status") or "").lower().strip()
        queue_status_by_match[match_number] = status_text
        if (
            ("queue" in status_text or "queu" in status_text or "on deck" in status_text)
            and "soon" not in status_text
        ):
            queueing_match_numbers.add(match_number)

        times_payload = nexus_match.get("times") or {}
        queue_time_ms = _extract_first_epoch_ms(
            times_payload,
            ("estimatedQueueTime", "estQueueTime", "queueTime"),
        )
        start_time_ms = _extract_first_epoch_ms(
            times_payload,
            ("estimatedStartTime", "estStartTime", "scheduledStartTime", "actualStartTime"),
        )

        try:
            if start_time_ms:
                start_local = datetime.fromtimestamp(start_time_ms / 1000, tz=dt_timezone.utc).astimezone(display_tz)
                start_eta_epoch_by_match[match_number] = int(start_local.timestamp())
            if queue_time_ms:
                local_dt = datetime.fromtimestamp(queue_time_ms / 1000, tz=dt_timezone.utc).astimezone(display_tz)
                queue_time_by_match[match_number] = local_dt.strftime("%I:%M %p").lstrip("0")
                queue_eta_epoch_by_match[match_number] = int(local_dt.timestamp())
        except Exception:
            continue

    return {
        "now_queuing": now_queuing,
        "announcements_display": announcements_display,
        "parts_requests_display": parts_requests_display,
        "current_match": current_match,
        "current_qual_match_num": current_qual_match_num,
        "queueing_match_numbers": queueing_match_numbers,
        "queue_time_by_match": queue_time_by_match,
        "queue_eta_epoch_by_match": queue_eta_epoch_by_match,
        "start_eta_epoch_by_match": start_eta_epoch_by_match,
        "queue_status_by_match": queue_status_by_match,
    }


def _extract_first_epoch_ms(times_payload, key_names):
    if not isinstance(times_payload, dict):
        return None
    for key_name in key_names:
        value = times_payload.get(key_name)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    return None


def _win_chance_class(win_chance_text):
    match = re.search(r"(\d+)", str(win_chance_text or ""))
    if not match:
        return "win-chance-unknown"
    value = int(match.group(1))
    if value >= 85:
        return "win-chance-excellent"
    if value >= 70:
        return "win-chance-good"
    if value >= 50:
        return "win-chance-lean-green"
    if value >= 30:
        return "win-chance-lean-red"
    return "win-chance-danger"


def _get_statbotics_session():
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        redirect=0,
        status=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        backoff_factor=0.2,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _get_nexus_session():
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        redirect=0,
        status=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        backoff_factor=0.2,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _derive_now_queuing_from_matches(nexus_matches):
    """
    Fallback when Nexus no longer returns top-level nowQueuing.
    Returns (label, match_number) from qualification match statuses/times.
    """
    if not isinstance(nexus_matches, list):
        return None, None

    qual_rows = []
    for row in nexus_matches:
        if not isinstance(row, dict):
            continue
        label = row.get("label") or ""
        match_number = _extract_qual_match_number(label, row)
        if match_number is None:
            continue
        qual_rows.append((match_number, label, row.get("status") or "", row.get("times") or {}))

    if not qual_rows:
        return None, None

    # Prefer explicit queueing status first.
    queueing_keywords = ("queue", "queu")
    queueing = []
    for match_number, label, status, times in qual_rows:
        status_text = str(status).lower()
        if any(keyword in status_text for keyword in queueing_keywords):
            est_q = times.get("estimatedQueueTime")
            queueing.append((est_q if isinstance(est_q, (int, float)) else 10**18, match_number, label, status))
    if queueing:
        queueing.sort(key=lambda item: (item[0], item[1]))
        _, match_number, label, status = queueing[0]
        return f"{label} ({status})", match_number

    # Next fallback: the most recent qualification currently on field.
    on_field = []
    for match_number, label, status, times in qual_rows:
        status_text = str(status).lower()
        if "on field" in status_text or "in progress" in status_text:
            actual_q = times.get("actualQueueTime")
            est_q = times.get("estimatedQueueTime")
            ts = actual_q if isinstance(actual_q, (int, float)) else (
                est_q if isinstance(est_q, (int, float)) else -1
            )
            on_field.append((ts, match_number, label, status))
    if on_field:
        on_field.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, match_number, label, status = on_field[0]
        return f"{label} ({status})", match_number

    # Last fallback: earliest upcoming qualification by estimated queue time.
    upcoming = []
    for match_number, label, status, times in qual_rows:
        est_q = times.get("estimatedQueueTime")
        if isinstance(est_q, (int, float)):
            upcoming.append((est_q, match_number, label, status))
    if upcoming:
        upcoming.sort(key=lambda item: (item[0], item[1]))
        _, match_number, label, status = upcoming[0]
        return f"{label} ({status})", match_number

    return None, None


def _derive_current_match_from_matches(nexus_matches):
    """
    Derive the currently playing match from Nexus match statuses.
    Returns (label, qualification_match_number_or_none).
    """
    if not isinstance(nexus_matches, list):
        return None, None

    active_matches = []
    for row in nexus_matches:
        if not isinstance(row, dict):
            continue
        label = row.get("label") or ""
        status_text = str(row.get("status") or "").lower()
        is_active = any(
            keyword in status_text
            for keyword in ("on field", "in progress", "playing", "in match", "underway")
        )
        if not is_active:
            continue

        times = row.get("times") or {}
        actual_field = times.get("actualOnFieldTime")
        est_field = times.get("estimatedOnFieldTime")
        ts = actual_field if isinstance(actual_field, (int, float)) else (
            est_field if isinstance(est_field, (int, float)) else (
                times.get("actualQueueTime") if isinstance(times.get("actualQueueTime"), (int, float)) else (
                    times.get("estimatedQueueTime") if isinstance(times.get("estimatedQueueTime"), (int, float)) else -1
                )
            )
        )
        qual_match_number = _extract_qual_match_number(label, row)
        sort_match_number = qual_match_number if isinstance(qual_match_number, int) else -1
        active_matches.append((ts, sort_match_number, label, row.get("status") or "On field", qual_match_number))

    if not active_matches:
        return None, None

    active_matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, _, label, status, qual_match_number = active_matches[0]
    return f"{label} ({status})", qual_match_number


def _format_playoff_label(comp_level, set_number, match_number):
    comp_map = {
        "ef": "EF",
        "qf": "QF",
        "sf": "SF",
        "f": "F",
    }
    prefix = comp_map.get((comp_level or "").lower(), (comp_level or "").upper())
    if set_number:
        return f"{prefix}{set_number}-M{match_number}"
    return f"{prefix}-M{match_number}"


def _infer_alliance_number(event, team_number):
    if not event or not team_number:
        return None
    value = TeamRanking.objects.filter(
        event=event,
        team__team_number=team_number,
    ).values_list("alliance_number", flat=True).first()
    if isinstance(value, int) and value > 0:
        return value
    return None


def _build_bracket_match_payload(match_obj, event=None):
    if not match_obj:
        return None
    blue_teams = [
        match_obj.team_blue_1.team_number,
        match_obj.team_blue_2.team_number,
        match_obj.team_blue_3.team_number,
    ]
    red_teams = [
        match_obj.team_red_1.team_number,
        match_obj.team_red_2.team_number,
        match_obj.team_red_3.team_number,
    ]
    blue_alliance_number = match_obj.blue_alliance_number
    red_alliance_number = match_obj.red_alliance_number
    if blue_alliance_number is None:
        blue_alliance_number = _infer_alliance_number(event, blue_teams[0])
    if red_alliance_number is None:
        red_alliance_number = _infer_alliance_number(event, red_teams[0])

    return {
        "blue_alliance_number": blue_alliance_number if blue_alliance_number is not None else "-",
        "red_alliance_number": red_alliance_number if red_alliance_number is not None else "-",
        "blue_teams_text": "-".join(str(team_number) for team_number in blue_teams),
        "red_teams_text": "-".join(str(team_number) for team_number in red_teams),
        "match_number": match_obj.match_number,
    }


def _format_parts_requests(parts_requests, display_tz):
    team_numbers = set()
    for item in parts_requests or []:
        if isinstance(item, dict):
            raw_team = (
                item.get("requestedByTeam")
                or item.get("teamNumber")
                or item.get("team_number")
                or item.get("team")
            )
            try:
                team_numbers.add(int(raw_team))
            except (TypeError, ValueError):
                continue

    team_name_map = {
        team.team_number: team.team_name
        for team in Team.objects.filter(team_number__in=team_numbers)
    }

    formatted = []
    for item in parts_requests or []:
        if isinstance(item, str):
            formatted.append({
                "team_number": "-",
                "requestor": "-",
                "item": item,
                "requested_at": "-",
            })
            continue

        if not isinstance(item, dict):
            continue

        team_number = (
            item.get("requestedByTeam")
            or item.get("teamNumber")
            or item.get("team_number")
            or item.get("team")
            or "-"
        )
        team_number_display = str(team_number)
        team_name = "-"
        try:
            team_number_int = int(team_number)
            team_name = team_name_map.get(team_number_int, "-")
            team_number_display = str(team_number_int)
        except (TypeError, ValueError):
            pass

        requestor = (
            item.get("requestor")
            or item.get("requester")
            or item.get("requestedBy")
            or item.get("name")
            or "-"
        )
        requested_item = (
            item.get("parts")
            or item.get("item")
            or item.get("part")
            or item.get("itemName")
            or item.get("request")
            or "Part request"
        )

        raw_ts = (
            item.get("postedTime")
            or item.get("requestedAt")
            or item.get("createdAt")
            or item.get("timestamp")
            or item.get("time")
        )
        requested_at = "-"
        try:
            if isinstance(raw_ts, (int, float)):
                ts = float(raw_ts)
                if ts > 10_000_000_000:
                    ts = ts / 1000.0
                local_dt = datetime.fromtimestamp(ts, tz=dt_timezone.utc).astimezone(display_tz)
                requested_at = local_dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
            elif isinstance(raw_ts, str) and raw_ts.strip():
                parsed = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt_timezone.utc)
                local_dt = parsed.astimezone(display_tz)
                requested_at = local_dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
        except Exception:
            requested_at = str(raw_ts) if raw_ts else "-"

        formatted.append({
            "team_number": team_number_display,
            "team_name": team_name,
            "requestor": requestor,
            "item": requested_item,
            "requested_at": requested_at,
        })
    return formatted


def _format_announcements(announcements, display_tz):
    formatted = []
    for item in announcements or []:
        if isinstance(item, str):
            formatted.append(
                {
                    "title": "Announcement",
                    "body": item,
                    "posted_at": "-",
                }
            )
            continue

        if not isinstance(item, dict):
            continue

        title = (
            item.get("title")
            or item.get("headline")
            or item.get("subject")
            or item.get("name")
            or item.get("type")
            or "Announcement"
        )
        body = (
            item.get("message")
            or item.get("text")
            or item.get("body")
            or item.get("announcement")
            or item.get("details")
            or item.get("content")
        )
        if not body:
            body = json.dumps(item, separators=(", ", ": "))

        raw_ts = (
            item.get("postedTime")
            or item.get("createdAt")
            or item.get("timestamp")
            or item.get("time")
            or item.get("date")
        )

        posted_at = "-"
        try:
            if isinstance(raw_ts, (int, float)):
                ts = float(raw_ts)
                if ts > 10_000_000_000:
                    ts = ts / 1000.0
                local_dt = datetime.fromtimestamp(ts, tz=dt_timezone.utc).astimezone(display_tz)
                posted_at = local_dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
            elif isinstance(raw_ts, str) and raw_ts.strip():
                parsed = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt_timezone.utc)
                local_dt = parsed.astimezone(display_tz)
                posted_at = local_dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
        except Exception:
            posted_at = str(raw_ts) if raw_ts else "-"

        formatted.append(
            {
                "title": str(title),
                "body": str(body),
                "posted_at": posted_at,
            }
        )
    return formatted


def _load_statbotics_rest_win_chances(event_key, team_number, matches):
    """
    Return a mapping of match_number -> display win chance for the given team.
    Uses Statbotics REST API per match key.
    """
    cache_key = f"pit_dash_statbotics:{event_key}:{team_number}"
    stale_cache_key = f"{cache_key}:stale"
    pulled_at_cache_key = f"{cache_key}:pulled_at"
    stale_pulled_at_cache_key = f"{stale_cache_key}:pulled_at"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached, None, cache.get(pulled_at_cache_key)
    stale_cached = cache.get(stale_cache_key)
    stale_map = stale_cached if isinstance(stale_cached, dict) else {}

    match_lookup = {m.match_number: m for m in matches}
    match_number_set = set(match_lookup.keys())
    if not match_number_set:
        return {}, None, None

    base_url = "https://api.statbotics.io/v3/matches"
    win_chance_by_match = {}
    had_request_error = False
    session = _get_statbotics_session()
    fetch_budget_seconds = 2.0 if stale_map else 6.0
    fetch_started = time.monotonic()

    try:
        response = session.get(
            base_url,
            params={
                "team": team_number,
                "event": event_key,
                "limit": max(100, len(match_number_set) + 20),
            },
            timeout=min(fetch_budget_seconds, 6.0),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        payload = []
        had_request_error = True
    except ValueError:
        payload = []
        had_request_error = True

    rows = payload if isinstance(payload, list) else []
    for row in rows:
        match_number = _parse_match_number_from_payload(row)
        if match_number is None or match_number not in match_number_set:
            continue

        team_prob = _extract_team_perspective_win_probability(row)
        if team_prob is not None:
            win_chance_by_match[match_number] = f"{round(team_prob * 100)}%"
            continue

        match_obj = match_lookup.get(match_number)
        if not match_obj:
            continue

        alliance = (row.get("alliance") or "").lower()
        if alliance not in {"red", "blue"}:
            alliance = _get_team_alliance(match_obj, team_number)
        if alliance is None:
            continue

        probability = _extract_alliance_win_probability(row, alliance)
        if probability is not None:
            win_chance_by_match[match_number] = f"{round(probability * 100)}%"

    # Fallback to per-match endpoint only for unresolved rows.
    unresolved = [n for n in match_number_set if n not in win_chance_by_match]
    remaining_budget = fetch_budget_seconds - (time.monotonic() - fetch_started)
    if remaining_budget <= 0:
        unresolved = []

    for match_number in unresolved[:3]:
        remaining_budget = fetch_budget_seconds - (time.monotonic() - fetch_started)
        if remaining_budget <= 0.25:
            break
        match_obj = match_lookup.get(match_number)
        if not match_obj:
            continue
        alliance = _get_team_alliance(match_obj, team_number)
        if alliance is None:
            continue

        match_key = f"{event_key}_qm{match_number}"
        try:
            response = session.get(
                f"https://api.statbotics.io/v3/match/{match_key}",
                timeout=min(0.9, max(0.25, remaining_budget)),
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            had_request_error = True
            continue
        except ValueError:
            had_request_error = True
            continue

        probability = _extract_alliance_win_probability(payload, alliance)
        if probability is not None:
            win_chance_by_match[match_number] = f"{round(probability * 100)}%"

    # If live API only resolves some matches, reuse stale values for the rest.
    for match_number in match_number_set:
        if match_number in win_chance_by_match:
            continue
        stale_value = stale_map.get(match_number)
        if stale_value:
            win_chance_by_match[match_number] = stale_value

    if win_chance_by_match:
        pulled_at = datetime.now(dt_timezone.utc).isoformat()
        cache.set(cache_key, win_chance_by_match, 120)
        cache.set(stale_cache_key, win_chance_by_match, 1800)
        cache.set(pulled_at_cache_key, pulled_at, 120)
        cache.set(stale_pulled_at_cache_key, pulled_at, 1800)
        return win_chance_by_match, None, pulled_at

    if had_request_error and stale_map:
        return stale_map, None, cache.get(stale_pulled_at_cache_key)
    if had_request_error:
        return {}, "Unable to load Statbotics win probabilities.", None
    return win_chance_by_match, None, None


@login_required()
def view_index(request):
    event = Event.objects.get(active=True)
    matches_list = Match.objects.filter(event_id=event).order_by('match_number')

    context = {
        'matches': matches_list
    }

    return render(request, 'scouting/index.html', context)


@login_required()
@permission_required('scouting.pit_scout_team', raise_exception=True)
def view_pit_scout_team_list(request):
    event = Event.objects.get(active=True)
    event_teams = event.teams.all().order_by('team_number')
    for team in event_teams:
        PitScoutData.objects.update_or_create(
            team=team,
            event=event,
        )

    pit_scout_reports = PitScoutData.objects.filter(event=event).order_by('team__team_number')

    context = {
        'pit_scout_reports': pit_scout_reports,
        'current_user': request.user,
    }

    return render(request, 'scouting/pitscoutteamlist.html', context)


@login_required()
@permission_required('scouting.pit_scout_team', raise_exception=True)
def view_pit_scout_team(request, team_number):
    team = Team.objects.get(team_number=team_number)
    event = Event.objects.get(active=True)
    pit_scout_data, created = PitScoutData.objects.get_or_create(team=team, event=event)

    if request.method == 'POST':
        form = PitScoutDataForm(request.POST, request.FILES, instance=pit_scout_data)
        if form.is_valid():
            form.save()
            return redirect('scouting:pit_scout_teams_list')
    else:
        form = PitScoutDataForm(instance=pit_scout_data)

    context = {
        'form': form,
        'pit_scout_data': pit_scout_data,
        'media_url': settings.MEDIA_URL,  # Added to help templates build image URLs
    }

    return render(request, 'scouting/pitscoutteam.html', context)
@login_required()
@permission_required('scouting.stands_scout_team', raise_exception=True)
def view_match(request, team_number, match_number):
    team = Team.objects.get(team_number=team_number)
    event = Event.objects.get(active=True)
    match = Match.objects.get(match_number=match_number, event_id=event)
    pit_scout_data = PitScoutData.objects.filter(team=team, event=event).first()

    # Check if a PitScoutData object already exists for this team and event
    match_data, created = MatchData2026.objects.get_or_create(team=team, match=match)

    if request.method == 'POST':
        # If the form has been submitted, create a form instance with the POST data and the existing PitScoutData object
        form = MatchData2026Form(request.POST, instance=match_data)
        print("Form POSTed")

        # Validate the form
        if form.is_valid():
            # Save the form data to the database
            form.save()

            # Redirect to the same page (or wherever you want to redirect to)
            return redirect('scouting:index')
    else:
        # If the form has not been submitted, create a form instance from the PitScoutData object
        form = MatchData2026Form(instance=match_data)

    robot_photo_urls = []
    if pit_scout_data:
        robot_photos = [pit_scout_data.robot_picture_1, pit_scout_data.robot_picture_2]
        robot_photo_urls = [
            _get_standscout_compressed_url(photo)
            for photo in robot_photos
            if photo
        ]
        robot_photo_urls = [url for url in robot_photo_urls if url]

    context = {
        'form': form,
        'match': match,
        'team': team,
        'robot_photo_urls': robot_photo_urls,
    }

    return render(request, 'scouting/match.html', context)


@login_required()
def view_team_statistics(request, team_number):
    team = get_object_or_404(Team, team_number=team_number)

    # Get active event
    active_event = Event.objects.filter(active=True).first()

    # Fetch match data for the team
    match_data = MatchData2026.objects.filter(team=team)

    # Count the number of matches played
    match_count = match_data.count()

    # Get pit scouting data for the active event
    pit_scout_data = PitScoutData.objects.filter(team=team, event=active_event).first()

    if pit_scout_data:
        pit_scout_data_dict = model_to_dict(pit_scout_data)
        image_fields = {
            'auton_picture_1',
            'auton_picture_2',
            'auton_picture_3',
            'robot_picture_1',
            'robot_picture_2',
        }
        # Remove non-display fields from table rows.
        for field_name in ['id', 'team', 'event', *image_fields]:
            pit_scout_data_dict.pop(field_name, None)

        # Format assigned scout name
        if pit_scout_data.assigned_scout:
            pit_scout_data_dict['assigned_scout'] = (
                f"{pit_scout_data.assigned_scout.first_name} "
                f"{pit_scout_data.assigned_scout.last_name}"
            ).strip()
        else:
            pit_scout_data_dict['assigned_scout'] = "No scout assigned"

        # Build display rows using field verbose names instead of raw db keys.
        pit_scout_data_rows = []
        for field_name, value in pit_scout_data_dict.items():
            if field_name == 'frc_nexus_url':
                # Show Nexus link via the pit_location row instead of raw URL row.
                continue

            label = pit_scout_data._meta.get_field(field_name).verbose_name
            if isinstance(value, bool):
                value = "Yes" if value else "No"

            row = {
                'label': str(label).title(),
                'value': value,
            }

            if field_name == 'pit_location' and value and pit_scout_data.frc_nexus_url:
                row['link_url'] = pit_scout_data.frc_nexus_url

            pit_scout_data_rows.append(row)

        # Gather images
        pit_scout_images = [
            pit_scout_data.auton_picture_1,
            pit_scout_data.auton_picture_2,
            pit_scout_data.auton_picture_3,
            pit_scout_data.robot_picture_1,
            pit_scout_data.robot_picture_2,
        ]
        # Filter out any `None` values
        pit_scout_images = [img for img in pit_scout_images if img]
    else:
        pit_scout_data_rows = []
        pit_scout_images = []

    # Get team ranking for the active event
    team_ranking = TeamRanking.objects.filter(team=team, event=active_event).first()

    context = {
        'team': team,
        'match_count': match_count,
        'pit_scout_data': pit_scout_data_rows,
        'pit_scout_images': pit_scout_images,
        'match_data': match_data,
        'team_ranking': team_ranking,
    }

    return render(request, 'scouting/statisticsteam.html', context)

@login_required
def update_priority(request):
    if request.method == "POST":
        try:
            team_number = request.POST.get("team_number")
            priority_value = request.POST.get("priority")

            if not team_number or not priority_value:
                return JsonResponse({"success": False, "error": "Missing team_number or priority"})

            priority_value = float(priority_value)  # Convert to integer

            if priority_value < 1 or priority_value > 10:
                return JsonResponse({"success": False, "error": "Priority must be between 1 and 10"})

            team = get_object_or_404(Team, team_number=team_number)
            event = get_object_or_404(Event, active=True)

            team_ranking, _ = TeamRanking.objects.get_or_create(team=team, event=event)
            team_ranking.priority = priority_value
            team_ranking.save()

            return JsonResponse({"success": True, "priority": priority_value})

        except ValueError:
            return JsonResponse({"success": False, "error": "Invalid priority value"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"})

@login_required()
def team_statistics_list(request):
    # Get sorting parameters from the request
    order_by = request.GET.get('order_by', 'team_number')  # Default to team_number
    direction = request.GET.get('direction', 'asc')

    # Validate order direction
    if direction not in ['asc', 'desc']:
        direction = 'asc'

    # Adjust ordering dynamically
    ordering = order_by if direction == 'asc' else f"-{order_by}"

    # Fetch and order teams
    teams = Team.objects.all().order_by(ordering)

    context = {
        'teams': teams,
        'order_by': order_by,
        'direction': direction,
    }
    return render(request, 'scouting/team_statistics_list.html', context)

from django.db.models import OuterRef, Subquery, Value

def view_picklist(request):
    event = Event.objects.get(active=True)
    sort_by = request.GET.get('sort', 'team_number')
    direction = request.GET.get('direction', 'asc')

    teams = list(event.teams.all())

    sortable_fields = [
        'rank',
        'opr',
        'dpr',
        'ccwm',
        'priority',
        'auto_tower_points',
        'total_auto_points',
        'total_teleop_points',
        'endgame_tower_points',
        'total_tower_points',
        'hub_total_fuel_count',
        'hub_teleop_fuel_count',
        'hub_endgame_fuel_count',
        'minor_foul_count',
        'major_foul_count',
        'foul_points',
    ]

    for team in teams:
        team.ranking, _ = TeamRanking.objects.get_or_create(
            team=team,
            event=event,
            defaults={'rank': 0}  # Set a default rank
        )

    reverse = direction == 'desc'
    if sort_by in sortable_fields:
        teams.sort(key=lambda t: getattr(t.ranking, sort_by) or 0, reverse=reverse)
    elif sort_by == 'team_number':
        teams.sort(key=lambda t: t.team_number, reverse=reverse)
    else:
        teams.sort(key=lambda t: t.team_number)

    return render(request, 'scouting/picklist.html', {
        'teams': teams,
        'event': event,
        'current_sort': sort_by,
        'current_direction': direction,
    })

def picklist_graphs(request):
    currentevent = Event.objects.get(active=True)
    teams_qs = currentevent.teams.all()
    teams_data = []

    for team in teams_qs:
        ranking, created = TeamRanking.objects.get_or_create(
            team=team,
            event=currentevent,
            defaults={'rank': 0}
        )
        teams_data.append({
            'team_number': team.team_number,
            'opr': ranking.opr or 0,
            'dpr': ranking.dpr or 0,
            'ccwm': ranking.ccwm or 0,
            'rank': ranking.rank or 0,
            'auto_tower_points': ranking.auto_tower_points or 0,
            'total_auto_points': ranking.total_auto_points or 0,
            'total_teleop_points': ranking.total_teleop_points or 0,
            'endgame_tower_points': ranking.endgame_tower_points or 0,
            'total_tower_points': ranking.total_tower_points or 0,
            'hub_auto_fuel_count': ranking.hub_auto_fuel_count or 0,
            'hub_teleop_fuel_count': ranking.hub_teleop_fuel_count or 0,
            'hub_endgame_fuel_count': ranking.hub_endgame_fuel_count or 0,
            'hub_total_fuel_count': ranking.hub_total_fuel_count or 0,
            'minor_foul_count': ranking.minor_foul_count or 0,
            'major_foul_count': ranking.major_foul_count or 0,
            'foul_points': ranking.foul_points or 0,
        })

    # Sort the teams_data by rank
    teams_data.sort(key=lambda x: x['rank'], reverse=True)

    # Now prepare lists for the graph context.
    context = {
        "teams": [d['team_number'] for d in teams_data],
        "opr_values": [round(d['opr'], 2) for d in teams_data],
        "dpr_values": [round(d['dpr'], 2) for d in teams_data],
        "ccwm_values": [round(d['ccwm'], 2) for d in teams_data],
        "rank_values": [d['rank'] for d in teams_data],
        "auto_tower_points_values": [round(d['auto_tower_points'], 2) for d in teams_data],
        "total_auto_points_values": [round(d['total_auto_points'], 2) for d in teams_data],
        "total_teleop_points_values": [round(d['total_teleop_points'], 2) for d in teams_data],
        "endgame_tower_points_values": [round(d['endgame_tower_points'], 2) for d in teams_data],
        "total_tower_points_values": [round(d['total_tower_points'], 2) for d in teams_data],
        "hub_auto_fuel_count_values": [round(d['hub_auto_fuel_count'], 2) for d in teams_data],
        "hub_teleop_fuel_count_values": [round(d['hub_teleop_fuel_count'], 2) for d in teams_data],
        "hub_endgame_fuel_count_values": [round(d['hub_endgame_fuel_count'], 2) for d in teams_data],
        "hub_total_fuel_count_values": [round(d['hub_total_fuel_count'], 2) for d in teams_data],
        "minor_foul_count_values": [round(d['minor_foul_count'], 2) for d in teams_data],
        "major_foul_count_values": [round(d['major_foul_count'], 2) for d in teams_data],
        "foul_points_values": [round(d['foul_points'], 2) for d in teams_data],
    }
    return render(request, "scouting/picklist_graphs.html", context)


@login_required()
def view_pit_dashboard(request):
    event = Event.objects.get(active=True)

    # Show Team 3637 schedule in the same table format as the match schedule.
    team_number = 3637
    team_matches = Match.objects.filter(
        event_id=event
    ).filter(
        team_red_1__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_red_2__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_red_3__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_blue_1__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_blue_2__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_blue_3__team_number=team_number
    )
    team_matches = team_matches.order_by("match_number").distinct()
    all_team_qual_matches = list(team_matches)

    nexus_status = {}
    announcements_display = []
    parts_requests = []
    parts_requests_display = []
    current_match = None
    now_queuing = None
    nexus_error = None
    current_qual_match_num = None
    queueing_match_numbers = set()
    queue_time_by_match = {}
    queue_eta_epoch_by_match = {}
    start_eta_epoch_by_match = {}
    queue_status_by_match = {}
    display_tz = ZoneInfo("America/New_York")
    statbotics_error = None
    statbotics_last_pulled_display = None
    win_chance_by_match = {}

    nexus_cache_key = f"pit_dash_nexus:{event.tba_event_key}"
    cached_nexus_status = cache.get(nexus_cache_key)
    nexus_fetch_timeout_seconds = 2.0 if isinstance(cached_nexus_status, dict) else 6.0
    if isinstance(cached_nexus_status, dict):
        nexus_status = cached_nexus_status
        parsed_nexus = _parse_nexus_dashboard_payload(nexus_status, display_tz)
        now_queuing = parsed_nexus["now_queuing"]
        announcements_display = parsed_nexus["announcements_display"]
        parts_requests_display = parsed_nexus["parts_requests_display"]
        current_match = parsed_nexus["current_match"]
        current_qual_match_num = parsed_nexus["current_qual_match_num"]
        queueing_match_numbers = parsed_nexus["queueing_match_numbers"]
        queue_time_by_match = parsed_nexus["queue_time_by_match"]
        queue_eta_epoch_by_match = parsed_nexus["queue_eta_epoch_by_match"]
        start_eta_epoch_by_match = parsed_nexus["start_eta_epoch_by_match"]
        queue_status_by_match = parsed_nexus["queue_status_by_match"]

    try:
        nexus_key = NexusApiKey.objects.get(active=True).api_key
        response = _get_nexus_session().get(
            f"https://frc.nexus/api/v1/event/{event.tba_event_key}",
            headers={"Nexus-Api-Key": nexus_key},
            timeout=nexus_fetch_timeout_seconds,
        )
        response.raise_for_status()
        live_nexus_status = response.json()
        if isinstance(live_nexus_status, dict):
            nexus_status = live_nexus_status
            cache.set(nexus_cache_key, live_nexus_status, 60)
            parsed_nexus = _parse_nexus_dashboard_payload(nexus_status, display_tz)
            now_queuing = parsed_nexus["now_queuing"]
            announcements_display = parsed_nexus["announcements_display"]
            parts_requests_display = parsed_nexus["parts_requests_display"]
            current_match = parsed_nexus["current_match"]
            current_qual_match_num = parsed_nexus["current_qual_match_num"]
            queueing_match_numbers = parsed_nexus["queueing_match_numbers"]
            queue_time_by_match = parsed_nexus["queue_time_by_match"]
            queue_eta_epoch_by_match = parsed_nexus["queue_eta_epoch_by_match"]
            start_eta_epoch_by_match = parsed_nexus["start_eta_epoch_by_match"]
            queue_status_by_match = parsed_nexus["queue_status_by_match"]
    except NexusApiKey.DoesNotExist:
        nexus_error = "No active Nexus API key configured."
    except requests.RequestException:
        if not isinstance(cached_nexus_status, dict):
            nexus_error = "Unable to load live event status from FRC Nexus."
    except ValueError:
        if not isinstance(cached_nexus_status, dict):
            nexus_error = "FRC Nexus returned invalid data."

    # Show a rolling window: 3 matches before now-queuing plus current/upcoming.
    if current_qual_match_num:
        team_matches = team_matches.filter(match_number__gte=max(1, current_qual_match_num - 3))

    # If no explicit queue status is available, fall back to the derived current qualification match.
    if not queueing_match_numbers and current_qual_match_num:
        queueing_match_numbers.add(current_qual_match_num)

    completed_match_numbers = set(
        MatchResult.objects.filter(
            match__event_id=event,
            is_final=True,
            match__match_number__isnull=False,
        ).values_list("match__match_number", flat=True)
    )
    shown_matches = [
        match_obj for match_obj in team_matches
        if match_obj.match_number not in completed_match_numbers
    ]
    win_chance_by_match, statbotics_error, statbotics_last_pulled = _load_statbotics_rest_win_chances(
        event_key=event.tba_event_key,
        team_number=team_number,
        matches=shown_matches,
    )
    if statbotics_last_pulled:
        try:
            parsed = datetime.fromisoformat(str(statbotics_last_pulled).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_timezone.utc)
            statbotics_last_pulled_display = parsed.astimezone(display_tz).strftime("%b %d, %I:%M:%S %p").replace(" 0", " ")
        except Exception:
            statbotics_last_pulled_display = str(statbotics_last_pulled)

    qual_rows = [
        {
            "match": m,
            "match_label": f"Q{m.match_number}",
            "queue_time": queue_time_by_match.get(m.match_number, "-"),
            "queue_eta_epoch": queue_eta_epoch_by_match.get(m.match_number),
            "start_eta_epoch": start_eta_epoch_by_match.get(m.match_number),
            "win_chance": win_chance_by_match.get(m.match_number, "-"),
            "win_chance_class": _win_chance_class(win_chance_by_match.get(m.match_number, "-")),
            "statbotics_match_url": f"https://www.statbotics.io/match/{event.tba_event_key}_qm{m.match_number}",
            "is_queueing": bool(current_qual_match_num and m.match_number <= current_qual_match_num),
            "blue_alliance_number": "-",
            "red_alliance_number": "-",
            "sort_group": 0,
            "sort_set": 0,
            "sort_match": m.match_number,
        }
        for m in shown_matches
    ]

    playoff_matches = (
        PlayoffMatch.objects.filter(event=event, is_final=False)
        .filter(
            team_red_1__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, is_final=False, team_red_2__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, is_final=False, team_red_3__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, is_final=False, team_blue_1__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, is_final=False, team_blue_2__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, is_final=False, team_blue_3__team_number=team_number
        )
    )
    playoff_matches = playoff_matches.distinct()
    all_team_playoff_matches = (
        PlayoffMatch.objects.filter(event=event)
        .filter(
            team_red_1__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, team_red_2__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, team_red_3__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, team_blue_1__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, team_blue_2__team_number=team_number
        ) | PlayoffMatch.objects.filter(
            event=event, team_blue_3__team_number=team_number
        )
    )
    all_team_playoff_matches = all_team_playoff_matches.distinct()
    comp_order = {"ef": 1, "qf": 2, "sf": 3, "f": 4}
    playoff_rows = [
        {
            "match": m,
            "match_label": _format_playoff_label(m.comp_level, m.set_number, m.match_number),
            "queue_time": "-",
            "queue_eta_epoch": None,
            "start_eta_epoch": None,
            "win_chance": "-",
            "win_chance_class": _win_chance_class("-"),
            "statbotics_match_url": f"https://www.statbotics.io/match/{m.tba_match_key}",
            "is_queueing": False,
            "blue_alliance_number": m.blue_alliance_number if m.blue_alliance_number is not None else "-",
            "red_alliance_number": m.red_alliance_number if m.red_alliance_number is not None else "-",
            "sort_group": comp_order.get((m.comp_level or "").lower(), 9),
            "sort_set": m.set_number or 0,
            "sort_match": m.match_number or 0,
        }
        for m in playoff_matches
    ]

    playoff_all_matches = list(
        PlayoffMatch.objects.select_related(
            "team_red_1", "team_red_2", "team_red_3",
            "team_blue_1", "team_blue_2", "team_blue_3",
        ).filter(event=event)
    )
    sf_matches = {
        int(m.set_number): m
        for m in playoff_all_matches
        if (m.comp_level or "").lower() == "sf" and m.set_number
    }
    playoff_bracket_slots = [_build_bracket_match_payload(sf_matches.get(i), event=event) for i in range(1, 14)]
    finals_payload = [
        _build_bracket_match_payload(m, event=event)
        for m in sorted(
            [m for m in playoff_all_matches if (m.comp_level or "").lower() == "f"],
            key=lambda item: item.match_number,
        )
    ]
    show_playoff_bracket = any(slot is not None for slot in playoff_bracket_slots) or bool(finals_payload)

    match_rows = sorted(
        qual_rows + playoff_rows,
        key=lambda row: (row["sort_group"], row["sort_set"], row["sort_match"]),
    )

    # Pull completed match results for Team 3637 from DB-synced TBA data.
    team_match_results = []
    completed_results = MatchResult.objects.select_related("match").filter(
        match__event_id=event,
        is_final=True,
        match__match_number__isnull=False,
    ).order_by("-match__match_number")

    for result in completed_results:
        match_obj = result.match
        alliance = _get_team_alliance(match_obj, team_number)
        if alliance not in {"red", "blue"}:
            continue
        if result.red_score is None or result.blue_score is None:
            continue

        our_score = result.red_score if alliance == "red" else result.blue_score
        opp_score = result.blue_score if alliance == "red" else result.red_score
        our_rp = result.red_rp if alliance == "red" else result.blue_rp

        if our_score > opp_score:
            outcome = "Win"
        elif our_score < opp_score:
            outcome = "Loss"
        else:
            outcome = "Tie"

        if our_rp is None:
            rp_display = "-"
        elif float(our_rp).is_integer():
            rp_display = str(int(our_rp))
        else:
            rp_display = f"{our_rp:.1f}"

        team_match_results.append(
            {
                "match_number": match_obj.match_number,
                "result": outcome,
                "score_display": f"{our_score}-{opp_score}",
                "rp_display": rp_display,
            }
        )

    our_rank = TeamRanking.objects.filter(
        event=event,
        team__team_number=team_number,
    ).values_list("rank", flat=True).first()
    total_teams = event.teams.count()
    matches_played = len(team_match_results)

    climbs_completed = 0
    for result in completed_results:
        match_obj = result.match
        alliance = _get_team_alliance(match_obj, team_number)
        if alliance == "red" and result.red_climb_success is True:
            climbs_completed += 1
        elif alliance == "blue" and result.blue_climb_success is True:
            climbs_completed += 1
    climb_success_rate = f"{climbs_completed} / {matches_played}"
    event_rank_rows = []
    for ranking in TeamRanking.objects.select_related("team").filter(
        event=event,
        rank__isnull=False,
    ).order_by("rank", "team__team_number"):
        is_null_team = (ranking.team.team_number == 0 and ranking.ranking_points is None)
        is_unranked_entry = (
            (ranking.rank in (0, None))
            and (ranking.ranking_points is None or float(ranking.ranking_points) <= 0.0)
        )
        event_rank_rows.append(
            {
                "team_number": "-" if is_null_team else ranking.team.team_number,
                "team_name": "Unassigned" if is_null_team else ranking.team.team_name,
                "rank": ranking.rank,
                "rank_display": "-" if is_unranked_entry else ranking.rank,
                "ranking_points": ranking.ranking_points,
                "is_null_team": is_null_team,
                "is_unranked_entry": is_unranked_entry,
                "_sort_team_number": ranking.team.team_number,
            }
        )

    # Push placeholder/null rows and unranked rank-0/no-RP rows to the bottom.
    event_rank_rows.sort(
        key=lambda row: (
            1 if row["is_null_team"] else 0,
            1 if row["is_unranked_entry"] else 0,
            row["rank"] if row["rank"] is not None else 10**6,
            row["_sort_team_number"],
        )
    )

    _our_rank = 0
    _other_rank = 60
    for team in event_rank_rows:
        if team['team_number'] == 4361:
            _other_rank = team['rank']
        if team['team_number'] == 3637:
            _our_rank = team['rank'] 
    rbd = _other_rank - _our_rank
    live_status = PitDashboardLiveStatus.objects.filter(event=event).first()
    live_match_data = None
    live_stream_match_number = None
    if live_status:
        source_ts = live_status.source_timestamp
        if source_ts is None:
            source_ts = live_status.modified

        staleness_seconds = None
        if source_ts:
            staleness_seconds = int(
                max(0, (datetime.now(dt_timezone.utc) - source_ts.astimezone(dt_timezone.utc)).total_seconds())
            )

        is_live_none = _looks_like_no_match_sample(
            live_status.match_label,
            live_status.game_time,
            live_status.blue_score,
            live_status.red_score,
        ) or not (live_status.match_label or "").strip()
        parsed_seconds_remaining = _parse_match_clock_to_seconds(live_status.game_time)
        if parsed_seconds_remaining is not None and parsed_seconds_remaining > 135:
            parsed_seconds_remaining = None
        live_stream_match_number = _extract_first_int(live_status.match_label)

        live_match_data = {
            "match_label": live_status.match_label or "?",
            "blue_score": _normalize_live_field(live_status.blue_score),
            "red_score": _normalize_live_field(live_status.red_score),
            "game_time": _normalize_live_field(live_status.game_time),
            "match_started": live_status.match_started,
            "last_update": source_ts.astimezone(display_tz) if source_ts else None,
            "is_stale": bool(staleness_seconds is not None and staleness_seconds > 35),
            "is_active_match": not is_live_none,
            "seconds_remaining": parsed_seconds_remaining,
        }

    next_match_alert = None
    next_match_clock = None
    queue_soon_window_seconds = 7 * 60 + 30
    queue_now_tolerance_seconds = 5
    queue_to_start_offsets = []
    for match_num, queue_epoch in queue_eta_epoch_by_match.items():
        start_epoch = start_eta_epoch_by_match.get(match_num)
        if not isinstance(start_epoch, int):
            continue
        delta = start_epoch - queue_epoch
        # Keep realistic deltas only.
        if 5 * 60 <= delta <= 60 * 60:
            queue_to_start_offsets.append(delta)
    queue_to_start_seconds = int(median(queue_to_start_offsets)) if queue_to_start_offsets else None

    if match_rows:
        next_row = match_rows[0]
        countdown_seconds = None
        est_start_seconds = None
        now_epoch = int(datetime.now(dt_timezone.utc).timestamp())

        eta_epoch = next_row.get("queue_eta_epoch")
        start_epoch = next_row.get("start_eta_epoch")
        if isinstance(start_epoch, int):
            est_start_seconds = max(0, start_epoch - now_epoch)

        if isinstance(eta_epoch, int):
            countdown_seconds = max(0, eta_epoch - now_epoch)
            if est_start_seconds is None and queue_to_start_seconds is not None:
                est_start_seconds = countdown_seconds + queue_to_start_seconds
        elif est_start_seconds is not None and queue_to_start_seconds is not None:
            # Derive queue ETA from start ETA only when we have observed Nexus queue->start offsets.
            countdown_seconds = max(0, est_start_seconds - queue_to_start_seconds)

        normalized_next_label = _normalize_label_for_compare(next_row.get("match_label"))
        normalized_now_queuing = _normalize_label_for_compare(now_queuing)
        normalized_current_match = _normalize_label_for_compare(current_match)
        next_match_is_now_queueing = bool(normalized_next_label and (
            normalized_next_label in normalized_now_queuing
            or normalized_next_label in normalized_current_match
        ))

        if (
            live_match_data
            and live_match_data.get("is_active_match")
            and isinstance(live_match_data.get("seconds_remaining"), int)
            and isinstance(live_stream_match_number, int)
        ):
            prev_match_number = max(0, int(next_row.get("sort_match", 0)) - 1)
            # Use live stream only as a secondary source when Nexus gave no usable countdown.
            if prev_match_number and live_stream_match_number == prev_match_number and countdown_seconds is None:
                seconds_remaining = int(live_match_data["seconds_remaining"])
                # Queueing threshold tied to field progression; do not force "now" without Nexus support.
                countdown_seconds = max(0, seconds_remaining - 60)
                if est_start_seconds is None and queue_to_start_seconds is not None:
                    est_start_seconds = countdown_seconds + queue_to_start_seconds

        # Do not show 00:00:00 unless this match is actually queueing now.
        if isinstance(countdown_seconds, int):
            if countdown_seconds <= 0 and next_match_is_now_queueing:
                countdown_seconds = 0
            elif countdown_seconds <= 0:
                countdown_seconds = 1

        queue_now = bool(isinstance(countdown_seconds, int) and countdown_seconds <= queue_now_tolerance_seconds)

        if isinstance(countdown_seconds, int):
            next_match_clock = {
                "match_label": next_row.get("match_label"),
                "countdown_seconds": countdown_seconds,
                "est_start_seconds": est_start_seconds,
            }

        show_queue_soon = (
            isinstance(countdown_seconds, int)
            and countdown_seconds > queue_now_tolerance_seconds
            and countdown_seconds <= queue_soon_window_seconds
        )
        if queue_now or show_queue_soon:
            alert_level = "now" if queue_now else "soon"
            next_match_alert = {
                "match_label": next_row.get("match_label"),
                "queue_now": queue_now,
                "level": alert_level,
                "status_text": "Queueing Now" if queue_now else "Queueing Soon",
                "countdown_seconds": countdown_seconds,
                "est_start_seconds": est_start_seconds,
                "reason": "Estimated",
            }

    local_recordings = []
    recording_library = []
    recording_match_options = {"qual": [], "playoff": []}
    if _is_localhost_or_local_ip(request):
        local_recordings = list(
            LivestreamRecording.objects.select_related("assigned_match", "assigned_playoff_match")
            .filter(event=event, assignment_completed=False)
            .order_by("-started_at")[:25]
        )
        local_recordings = [
            rec for rec in local_recordings
            if rec.is_active or _recording_file_exists(rec)
        ]
        recording_library = list(
            LivestreamRecording.objects.select_related("assigned_match", "assigned_playoff_match")
            .filter(event=event, is_active=False)
            .order_by("-started_at")[:200]
        )
        recording_library = [rec for rec in recording_library if _recording_file_exists(rec)]
        recording_match_options["qual"] = [
            {"id": m.id, "label": f"Q{m.match_number}"}
            for m in sorted(all_team_qual_matches, key=lambda item: item.match_number)
        ]
        recording_match_options["playoff"] = [
            {
                "id": m.id,
                "label": _format_playoff_label(m.comp_level, m.set_number, m.match_number),
            }
            for m in sorted(
                list(all_team_playoff_matches),
                key=lambda item: (comp_order.get((item.comp_level or "").lower(), 9), item.set_number or 0, item.match_number or 0),
            )
        ]

    context = {
        "event": event,
        "team_number": team_number,
        "match_rows": match_rows,
        "show_alliance_number_columns": bool(playoff_rows),
        "playoff_bracket_slots": playoff_bracket_slots,
        "playoff_finals_payload": finals_payload,
        "show_playoff_bracket": show_playoff_bracket,
        "team_match_results": team_match_results,
        "our_rank": our_rank,
        "total_teams": total_teams,
        "matches_played": matches_played,
        "RBD" : rbd,
        "climb_success_rate": climb_success_rate,
        "event_rank_rows": event_rank_rows,
        "current_match": current_match,
        "now_queuing": now_queuing,
        "announcements": announcements_display,
        "parts_requests": parts_requests_display,
        "nexus_error": nexus_error,
        "statbotics_error": statbotics_error,
        "statbotics_last_pulled_display": statbotics_last_pulled_display,
        "robot_nt_status": "n",
        "show_rsl_wall": _is_localhost_or_local_ip(request),
        "live_match_data": live_match_data,
        "next_match_clock": next_match_clock,
        "next_match_alert": next_match_alert,
        "local_recordings": local_recordings,
        "recording_library": recording_library,
        "recording_match_options": recording_match_options,
    }
    return render(request, "scouting/pit_dashboard.html", context)


def view_recording_control(request):
    active_event = Event.objects.filter(active=True).first()

    if request.method == "POST":
        action = str(request.POST.get("action") or "").strip().lower()
        if action == "start":
            ok, msg, _ = start_recording(event=active_event)
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        elif action == "stop":
            ok, msg, _ = stop_recording()
            if ok:
                messages.success(request, msg)
            else:
                messages.warning(request, msg)
        else:
            messages.error(request, "Invalid action.")
        return redirect("scouting:recording_control")

    active_recording = get_active_recording()
    preflight = get_recording_source_preflight()
    recent_recordings = list(LivestreamRecording.objects.order_by("-started_at")[:40])
    recent_recordings = [
        rec for rec in recent_recordings
        if rec.is_active or _recording_file_exists(rec)
    ][:20]
    media_base = "/" + str(settings.MEDIA_URL).strip("/") + "/"
    public_control_url = request.build_absolute_uri(request.path)

    context = {
        "active_event": active_event,
        "active_recording": active_recording,
        "recent_recordings": recent_recordings,
        "media_base": media_base,
        "public_control_url": public_control_url,
        "source_url": str(getattr(settings, "LIVESTREAM_SOURCE_URL", "") or ""),
        "preflight": preflight,
    }
    return render(request, "scouting/recording_control.html", context)


@login_required()
@require_POST
def assign_recording_to_match(request, recording_id):
    if not _is_localhost_or_local_ip(request):
        return HttpResponseForbidden("Local access only.")

    recording = get_object_or_404(LivestreamRecording, id=recording_id)
    assignment_type = str(request.POST.get("assignment_type") or "").strip().lower()
    note = str(request.POST.get("assignment_note") or "").strip()[:120]

    recording.assigned_match = None
    recording.assigned_playoff_match = None
    recording.assignment_note = note
    recording.assignment_completed = True

    if assignment_type == "qual":
        match_id = request.POST.get("qual_match_id")
        if match_id:
            recording.assigned_match = Match.objects.filter(id=match_id).first()
    elif assignment_type == "playoff":
        playoff_id = request.POST.get("playoff_match_id")
        if playoff_id:
            recording.assigned_playoff_match = PlayoffMatch.objects.filter(id=playoff_id).first()

    recording.save(
        update_fields=[
            "assigned_match",
            "assigned_playoff_match",
            "assignment_note",
            "assignment_completed",
            "modified",
        ]
    )
    return redirect("scouting:pit_dashboard")


@login_required()
@require_POST
def open_recording_local(request, recording_id):
    if not _is_localhost_or_local_ip(request):
        return HttpResponseForbidden("Local access only.")

    recording = get_object_or_404(LivestreamRecording, id=recording_id)
    ok, message = open_recording_or_folder(recording)
    return JsonResponse({"ok": ok, "message": message}, status=200 if ok else 400)


@login_required()
@require_POST
def pit_dashboard_spawn_terminals(request):
    if not _is_localhost_or_local_ip(request):
        return HttpResponseForbidden("Local access only.")

    if os.name != "nt":
        return JsonResponse(
            {"ok": False, "message": "Windows terminal spawning only works on Windows hosts."},
            status=400,
        )

    try:
        requested = int(str(request.POST.get("count") or "10").strip())
    except (TypeError, ValueError):
        requested = 10
    spawn_count = max(1, min(requested, 10))

    spawned = 0
    for idx in range(spawn_count):
        try:
            cmd = (
                f"title Popup Terminal {idx + 1} & "
                "echo Running popup protocol... & "
                "start /b tree C:\\ >nul 2>&1 & "
                "timeout /t 4 >nul"
            )
            subprocess.Popen(
                ["cmd.exe", "/c", cmd],
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            spawned += 1
        except Exception:
            pass
        time.sleep(0.08)

    ok = spawned == spawn_count
    return JsonResponse(
        {
            "ok": ok,
            "spawned": spawned,
            "requested": spawn_count,
            "message": f"Spawned {spawned}/{spawn_count} Windows terminals.",
        },
        status=200 if spawned > 0 else 500,
    )


@login_required()
def pit_dashboard_robot_status(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    return JsonResponse(_get_robot_status_payload_from_nt())


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def pit_dashboard_live_feed_ingest(request):
    configured_token = str(getattr(settings, "PIT_DASH_INGEST_TOKEN", "") or "").strip()
    if configured_token:
        provided_token = str(request.headers.get("X-Pit-Ingest-Token", "")).strip()
        if provided_token != configured_token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        event = Event.objects.get(active=True)
    except Event.DoesNotExist:
        return JsonResponse({"error": "No active event configured"}, status=400)

    payload = request.data if isinstance(request.data, dict) else {}
    match_label = _normalize_live_field(payload.get("match"), default="")
    game_time = _normalize_live_field(payload.get("game_time"))
    blue_score = _normalize_live_field(payload.get("blue_score"))
    red_score = _normalize_live_field(payload.get("red_score"))

    source_timestamp = parse_datetime(str(payload.get("timestamp") or "").strip())
    if source_timestamp is None:
        source_timestamp = datetime.now(dt_timezone.utc)
    elif source_timestamp.tzinfo is None:
        source_timestamp = source_timestamp.replace(tzinfo=dt_timezone.utc)

    status_obj, _ = PitDashboardLiveStatus.objects.get_or_create(event=event)
    if _is_intermediate_period_sample(status_obj, match_label, game_time, blue_score, red_score):
        status_obj.source_timestamp = source_timestamp
        status_obj.match_label = ""
        status_obj.game_time = "?"
        status_obj.blue_score = "?"
        status_obj.red_score = "?"
        status_obj.match_started = None
        status_obj.last_raw_payload = payload
        status_obj.save(
            update_fields=[
                "source_timestamp",
                "match_label",
                "game_time",
                "blue_score",
                "red_score",
                "match_started",
                "last_raw_payload",
                "modified",
            ]
        )
        return JsonResponse({"status": "intermediate_period"})

    match_started = _infer_match_started(
        previous_status=status_obj,
        new_match=match_label,
        new_time=game_time,
        new_blue_score=blue_score,
        new_red_score=red_score,
    )

    status_obj.source_timestamp = source_timestamp
    status_obj.match_label = match_label
    status_obj.game_time = game_time
    status_obj.blue_score = blue_score
    status_obj.red_score = red_score
    status_obj.match_started = match_started
    status_obj.last_raw_payload = payload
    status_obj.save(
        update_fields=[
            "source_timestamp",
            "match_label",
            "game_time",
            "blue_score",
            "red_score",
            "match_started",
            "last_raw_payload",
            "modified",
        ]
    )

    return JsonResponse(
        {
            "status": "ok",
            "match": status_obj.match_label,
            "game_time": status_obj.game_time,
            "match_started": status_obj.match_started,
        }
    )


@api_view(['POST'])  # Specify the allowed HTTP methods
@authentication_classes([TokenAuthentication])  # Use TokenAuthentication
@permission_classes([IsAuthenticated])  # Require authenticated users
def sync_data(request):
    if request.method == 'POST':
        # Deserialize the data back into Django objects
        for obj in serializers.deserialize('json', request.body):
            # If the object already exists, update it. Otherwise, create a new one.
            obj.save()

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error'}, status=400)
