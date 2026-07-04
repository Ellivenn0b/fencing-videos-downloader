"""Téléchargement et découpe des extraits (YouTube via yt-dlp, flux m3u8 via FFmpeg)."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import imageio_ffmpeg
import yt_dlp
from yt_dlp.utils import download_range_func

from fencing_videos_downloader.utils import format_timestamp, generate_clip_name, unique_path

ProgressCallback = Callable[[Optional[float]], None]  # 0..1, None = indéterminé
StatusCallback = Callable[[str], None]


class DownloadError(Exception):
    """Erreur présentable telle quelle à l'utilisateur."""


def is_stream_url(url: str) -> bool:
    """Vrai si l'URL pointe vers un flux HLS (m3u8) plutôt qu'une page vidéo."""
    return ".m3u8" in url.lower()


@dataclass(frozen=True)
class ClipRequest:
    url: str
    start: int  # secondes
    end: int  # secondes
    dest_dir: Path
    name: str | None = None  # sans extension ; None = nom généré

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("l'horodatage de fin doit être après celui de début")


def _ffmpeg_exe() -> str:
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise DownloadError(
            "FFmpeg est introuvable dans l'application. Réinstallez-la."
        ) from exc


def _popen_options() -> dict:
    # Sans ce drapeau, chaque appel à FFmpeg ouvrirait une console sous Windows.
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _escape_outtmpl(text: str) -> str:
    # Les « % » littéraux doivent être doublés dans un gabarit yt-dlp.
    return text.replace("%", "%%")


class _SilentLogger:
    """yt-dlp est bavard ; les erreurs remontent déjà par les exceptions."""

    def debug(self, message: str) -> None: ...

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...


def download_youtube_clip(
    request: ClipRequest,
    on_progress: ProgressCallback,
    on_status: StatusCallback,
) -> Path:
    """Télécharge l'extrait demandé d'une vidéo YouTube et renvoie le fichier créé."""
    on_status("Analyse de la vidéo…")

    if request.name:
        target = unique_path(request.dest_dir, request.name)
        outtmpl = _escape_outtmpl(str(target.parent / target.stem)) + ".%(ext)s"
    else:
        clip_range = f" ({format_timestamp(request.start)}-{format_timestamp(request.end)})"
        outtmpl = os.path.join(
            _escape_outtmpl(str(request.dest_dir)),
            "%(title)s" + _escape_outtmpl(clip_range) + ".%(ext)s",
        )

    def hook(data: dict) -> None:
        if data["status"] == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            if total:
                on_progress(data.get("downloaded_bytes", 0) / total)
            else:
                on_progress(None)
        elif data["status"] == "finished":
            on_status("Assemblage du fichier…")
            on_progress(None)

    options = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "download_ranges": download_range_func(None, [(request.start, request.end)]),
        "force_keyframes_at_cuts": True,
        "ffmpeg_location": _ffmpeg_exe(),
        "noplaylist": True,
        "retries": 3,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _SilentLogger(),
        "progress_hooks": [hook],
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            on_status("Téléchargement de l'extrait…")
            info = ydl.extract_info(request.url, download=True)
            result = _resolve_output(info, ydl)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(_friendly_youtube_error(str(exc))) from exc

    on_progress(1.0)
    return result


def _resolve_output(info: dict | None, ydl: yt_dlp.YoutubeDL) -> Path:
    for entry in (info or {}).get("requested_downloads") or []:
        if entry.get("filepath"):
            return Path(entry["filepath"])
    return Path(ydl.prepare_filename(info))


def _friendly_youtube_error(message: str) -> str:
    text = message.removeprefix("ERROR: ")
    lowered = text.lower()
    if "unsupported url" in lowered or "not a valid url" in lowered:
        return "Cette URL n'est pas reconnue. Vérifiez le lien puis réessayez."
    if "video unavailable" in lowered:
        return "Vidéo indisponible (supprimée, privée ou bloquée dans votre pays)."
    if "sign in" in lowered or "login required" in lowered:
        return "Cette vidéo exige une connexion à un compte ; impossible de la télécharger."
    if (
        "getaddrinfo" in lowered
        or "urlopen" in lowered
        or "network" in lowered
        or "timed out" in lowered
    ):
        return "Connexion impossible. Vérifiez votre accès Internet puis réessayez."
    return f"Le téléchargement a échoué : {text[:250]}"


def download_stream_clip(
    request: ClipRequest,
    on_progress: ProgressCallback,
    on_status: StatusCallback,
) -> Path:
    """Découpe l'extrait demandé d'un flux m3u8 (copie directe, sans ré-encodage)."""
    stem = request.name or generate_clip_name("clip_fencingtv")
    output = unique_path(request.dest_dir, stem)
    duration = request.end - request.start

    on_status("Connexion au flux…")
    on_progress(None)

    command = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-nostdin",
        # « error » garde stderr assez court pour ne pas saturer le tube.
        "-loglevel", "error",
        "-ss", str(request.start),
        "-i", request.url,
        "-t", str(duration),
        "-c", "copy",
        "-movflags", "+faststart",
        "-avoid_negative_ts", "make_zero",
        "-progress", "pipe:1",
        "-y", str(output),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_popen_options(),
    )

    assert process.stdout is not None
    downloading_announced = False
    for line in process.stdout:
        key, _, value = line.strip().partition("=")
        if key == "out_time_us" and value.isdigit():
            if not downloading_announced:
                on_status("Téléchargement du clip…")
                downloading_announced = True
            on_progress(min(int(value) / 1_000_000 / duration, 1.0))

    stderr_output = process.stderr.read() if process.stderr else ""
    if process.wait() != 0:
        output.unlink(missing_ok=True)  # ne pas laisser un fichier corrompu
        raise DownloadError(_friendly_ffmpeg_error(stderr_output))
    if not output.exists():
        raise DownloadError("FFmpeg n'a produit aucun fichier. Vérifiez le lien du flux.")

    on_progress(1.0)
    return output


def _friendly_ffmpeg_error(stderr: str) -> str:
    lowered = stderr.lower()
    if "404" in stderr or "not found" in lowered:
        return "Flux introuvable (erreur 404). Le lien m3u8 a peut-être expiré."
    if "403" in stderr or "forbidden" in lowered:
        return "Accès refusé au flux (erreur 403). Le lien a peut-être expiré."
    if (
        "failed to resolve" in lowered
        or "connection" in lowered
        or "network" in lowered
        or "timed out" in lowered
    ):
        return "Connexion au flux impossible. Vérifiez le lien et votre accès Internet."
    if "invalid data" in lowered:
        return "Ce lien ne semble pas être un flux vidéo valide (m3u8 attendu)."
    last_line = stderr.strip().splitlines()[-1] if stderr.strip() else "raison inconnue"
    return f"FFmpeg a échoué : {last_line[:250]}"
