"""Fonctions utilitaires : horodatages, noms de fichiers, chemins."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_FILENAME_LENGTH = 150


def resource_path(relative: str | Path) -> Path:
    """Chemin d'une ressource embarquée (compatible PyInstaller)."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir) / relative
    return Path(__file__).resolve().parent.parent / relative


def parse_timestamp(text: str) -> int:
    """Convertit « ss », « mm:ss » ou « hh:mm:ss » en secondes."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("format attendu : mm:ss ou hh:mm:ss")
    parts = cleaned.split(":")
    if len(parts) > 3 or not all(part.strip().isdigit() for part in parts):
        raise ValueError("format attendu : mm:ss ou hh:mm:ss")
    values = [int(part) for part in parts]
    if any(value > 59 for value in values[1:]):
        raise ValueError("les minutes et secondes doivent être inférieures à 60")
    seconds = 0
    for value in values:
        seconds = seconds * 60 + value
    return seconds


def format_timestamp(seconds: int) -> str:
    """Formate une durée en texte compact utilisable dans un nom de fichier."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def sanitize_filename(name: str) -> str:
    """Retire les caractères interdits par les systèmes de fichiers."""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", name).strip(" .")
    return cleaned[:_MAX_FILENAME_LENGTH]


def generate_clip_name(prefix: str) -> str:
    """Nom par défaut horodaté, unique à la seconde près."""
    return f"{prefix}_{datetime.now():%Y-%m-%d_%Hh%Mm%Ss}"


def unique_path(directory: Path, stem: str, suffix: str = ".mp4") -> Path:
    """Chemin qui n'écrase jamais un fichier existant (ajoute « (2) », « (3) »…)."""
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        counter += 1
        candidate = directory / f"{stem} ({counter}){suffix}"
    return candidate


def desktop_dir() -> Path:
    """Dossier Bureau de l'utilisateur, avec repli sur le dossier personnel."""
    if sys.platform == "win32":
        desktop = _windows_desktop()
        if desktop is not None:
            return desktop
    if sys.platform.startswith("linux"):
        desktop = _linux_xdg_desktop()
        if desktop is not None:
            return desktop
    fallback = Path.home() / "Desktop"
    return fallback if fallback.is_dir() else Path.home()


def _windows_desktop() -> Path | None:
    """Bureau via l'API Windows (gère la redirection OneDrive, ex. « Bureau »)."""
    try:
        import ctypes
        from ctypes import wintypes

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        folder_id = _GUID(
            0xB4BFCC3A,
            0xDB2C,
            0x424C,
            (wintypes.BYTE * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41),
        )
        path_ptr = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(path_ptr)
        )
        if result == 0 and path_ptr.value:
            path = Path(path_ptr.value)
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
            if path.is_dir():
                return path
    except Exception:
        pass
    return None


def _linux_xdg_desktop() -> Path | None:
    """Bureau déclaré dans ~/.config/user-dirs.dirs (localisé selon la langue)."""
    config = Path.home() / ".config" / "user-dirs.dirs"
    try:
        match = re.search(
            r'XDG_DESKTOP_DIR="([^"]+)"', config.read_text(encoding="utf-8")
        )
    except OSError:
        return None
    if match is None:
        return None
    path = Path(match.group(1).replace("$HOME", str(Path.home())))
    return path if path.is_dir() else None
