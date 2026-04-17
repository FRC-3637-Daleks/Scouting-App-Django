import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.utils import timezone as dj_timezone

from .models import LivestreamRecording


_ACTIVE_PROCESS = None


def _is_windows():
    return os.name == "nt"


def _is_pid_running(pid):
    if not pid:
        return False
    if _is_windows():
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            output = (result.stdout or "") + (result.stderr or "")
            return str(int(pid)) in output
        except Exception:
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _resolve_stream_url(source_url):
    try:
        import yt_dlp  # type: ignore

        ydl_opts = {
            "format": "best[height<=720]/best",
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
            resolved = info.get("url")
            if resolved:
                return resolved, True
    except Exception:
        pass
    return source_url, False


def _get_ffmpeg_path():
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _get_vlc_path():
    configured = str(getattr(settings, "VLC_PATH", "") or "").strip()
    if configured and Path(configured).exists():
        return configured

    from_path = shutil.which("vlc")
    if from_path:
        return from_path

    if os.name == "nt":
        candidates = [
            Path("C:/Program Files/VideoLAN/VLC/vlc.exe"),
            Path("C:/Program Files (x86)/VideoLAN/VLC/vlc.exe"),
        ]
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "Programs/VideoLAN/VLC/vlc.exe")

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

    return None


def _get_recordings_dir():
    subdir = str(getattr(settings, "LIVESTREAM_RECORDINGS_SUBDIR", "recordings") or "recordings")
    output_dir = Path(settings.MEDIA_ROOT) / subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir, subdir.strip("/\\")


def _sync_active_state():
    active = LivestreamRecording.objects.filter(is_active=True).order_by("-started_at").first()
    if not active:
        return None
    if _is_pid_running(active.ffmpeg_pid):
        return active
    active.is_active = False
    active.stopped_at = active.stopped_at or dj_timezone.now()
    active.save(update_fields=["is_active", "stopped_at", "modified"])
    return None


def get_active_recording():
    return _sync_active_state()


def start_recording(event=None):
    existing = _sync_active_state()
    if existing:
        return False, "A recording is already in progress.", existing

    ffmpeg_path = _get_ffmpeg_path()
    if not ffmpeg_path:
        return False, "ffmpeg is not installed or not in PATH.", None

    source_url = str(getattr(settings, "LIVESTREAM_SOURCE_URL", "") or "").strip()
    if not source_url:
        return False, "LIVESTREAM_SOURCE_URL is not configured.", None

    stream_url, extracted = _resolve_stream_url(source_url)
    source_lower = source_url.lower()
    if ("youtube.com" in source_lower or "youtu.be" in source_lower) and not extracted:
        return False, "Install yt-dlp in the server environment to record YouTube streams.", None
    output_dir, subdir = _get_recordings_dir()
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
    filename = f"match_recording_{stamp}.mp4"
    output_abs = output_dir / filename
    output_rel = f"{subdir}/{filename}".replace("\\", "/")

    command = [
        ffmpeg_path,
        "-y",
        "-i",
        stream_url,
        "-vf",
        "scale=-2:720",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-movflags",
        "+faststart",
        str(output_abs),
    ]

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        return False, f"Could not start ffmpeg: {exc}", None

    global _ACTIVE_PROCESS
    _ACTIVE_PROCESS = process

    recording = LivestreamRecording.objects.create(
        event=event,
        source_url=source_url,
        output_file=output_rel,
        ffmpeg_pid=process.pid,
        is_active=True,
        started_at=dj_timezone.now(),
    )
    return True, "Recording started.", recording


def stop_recording():
    recording = LivestreamRecording.objects.filter(is_active=True).order_by("-started_at").first()
    if not recording:
        return False, "No active recording to stop.", None

    stopped = False
    pid = recording.ffmpeg_pid
    global _ACTIVE_PROCESS

    if _ACTIVE_PROCESS and _ACTIVE_PROCESS.poll() is None and _ACTIVE_PROCESS.pid == pid:
        try:
            if _ACTIVE_PROCESS.stdin:
                _ACTIVE_PROCESS.stdin.write(b"q\n")
                _ACTIVE_PROCESS.stdin.flush()
            _ACTIVE_PROCESS.wait(timeout=10)
            stopped = True
        except Exception:
            stopped = False

    if not stopped and _is_pid_running(pid):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T"], timeout=10, check=False)
            stopped = not _is_pid_running(pid)
        except Exception:
            stopped = False

    if not stopped and _is_pid_running(pid):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=10, check=False)
            stopped = not _is_pid_running(pid)
        except Exception:
            stopped = False

    recording.is_active = False
    recording.stopped_at = dj_timezone.now()
    recording.save(update_fields=["is_active", "stopped_at", "modified"])
    _ACTIVE_PROCESS = None

    if stopped:
        return True, "Recording stopped.", recording
    return False, "Recording process ended with warnings.", recording


def open_recording_or_folder(recording):
    rel_path = str(getattr(recording, "output_file", "") or "").strip().replace("\\", "/")
    if not rel_path:
        return False, "Recording file path is missing."

    abs_path = Path(settings.MEDIA_ROOT) / rel_path
    recordings_dir = abs_path.parent

    if abs_path.is_file():
        vlc_path = _get_vlc_path()
        if vlc_path:
            try:
                subprocess.Popen([vlc_path, str(abs_path)])
                return True, f"Opened recording in VLC ({vlc_path})."
            except Exception as exc:
                vlc_error = str(exc)
        else:
            vlc_error = "VLC executable not found"

        # Next best: open the video with system default app.
        try:
            if os.name == "nt":
                os.startfile(str(abs_path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(abs_path)])
            else:
                subprocess.Popen(["xdg-open", str(abs_path)])
            return True, "Opened recording in default video player."
        except Exception as exc:
            default_app_error = str(exc)
    else:
        vlc_error = "Recording file missing"
        default_app_error = "Recording file missing"

    # Fallback: open the folder that contains recordings.
    try:
        if os.name == "nt":
            os.startfile(str(recordings_dir))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(recordings_dir)])
        else:
            subprocess.Popen(["xdg-open", str(recordings_dir)])
        return True, (
            "Opened recordings folder. "
            f"VLC: {vlc_error}. Default app: {default_app_error}."
        )
    except Exception as exc:
        return False, f"Could not open VLC or recordings folder: {exc}"
