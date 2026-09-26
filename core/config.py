"""
Application configuration and cross-platform path handling.

Keeps all filesystem/OS-specific decisions in one place so the rest of
the application never has to know whether it is running on Windows or
macOS (NFR-08 Portability).
"""
from __future__ import annotations

import os
import sys
import platform
from pathlib import Path

APP_NAME = "HaramaIn"
APP_VENDOR = "HaramaIn by Sheraz"
APP_VERSION = "1.0.0"

DEFAULT_CHARGE_PKR = 200.0
DEFAULT_TRANSFER_HOURS = 6
DEFAULT_REMINDER_DAYS = 2
CURRENCY_SYMBOL = "PKR"
DEFAULT_THEME_NAME = "Glass Gold"
# Colour used for pilgrims whose permit is inside the reminder window (red by default).
DEFAULT_UPCOMING_COLOR = "#e0455c"

# FR-PASS-01/02: every pilgrim password ends with this suffix.
PASSWORD_SUFFIX = "111@"

# Filenames searched (in order) when looking for the business logo.
LOGO_FILENAMES = ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp", "logo.bmp", "logo.ico")


def get_app_data_dir() -> Path:
    """
    Returns the correct per-user application data directory for the
    current OS, creating it if necessary.

    Windows -> %APPDATA%\\HaramaIn
    macOS   -> ~/Library/Application Support/HaramaIn
    Linux   -> ~/.local/share/HaramaIn   (fallback, useful for dev/testing)
    """
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / APP_NAME
    elif system == "Darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_documents_export_dir() -> Path:
    """Default location offered when saving PDF bills / exports."""
    system = platform.system()
    if system == "Windows":
        path = Path.home() / "Documents" / APP_NAME
    elif system == "Darwin":
        path = Path.home() / "Documents" / APP_NAME
    else:
        path = Path.home() / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_app_data_dir() / "harmain.db"


def get_documents_storage_dir() -> Path:
    """Where uploaded passport/visa documents are securely stored."""
    path = get_app_data_dir() / "documents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_photos_storage_dir() -> Path:
    """Where pilgrim photos (auto-picked from a document, or set by hand) are stored."""
    path = get_app_data_dir() / "photos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_backup_dir() -> Path:
    path = get_app_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


# Name of the subfolder created inside iCloud Drive / Google Drive so the
# backup never gets mixed up with the administrator's own files there.
CLOUD_BACKUP_FOLDER_NAME = "HaramaIn Backup"


def detect_icloud_drive_dir() -> Path | None:
    """
    Best-effort detection of the local folder that the iCloud Drive
    desktop client keeps in sync. Returns None if iCloud Drive does not
    appear to be installed/signed in - the administrator can still type
    or browse to a folder manually in Settings -> Backup & Sync.

    Windows (iCloud for Windows): the classic location is
    <home>\\iCloudDrive. Some installs instead use the "iCloudDrive"
    folder mirrored under "iCloud Drive" in File Explorer's Quick
    Access, which resolves to the same path.
    macOS: iCloud Drive always lives at
    ~/Library/Mobile Documents/com~apple~CloudDocs.
    """
    system = platform.system()
    home = Path.home()
    candidates: list[Path] = []
    if system == "Windows":
        candidates += [
            home / "iCloudDrive",
            home / "iCloud Drive",
        ]
    elif system == "Darwin":
        candidates.append(home / "Library" / "Mobile Documents" / "com~apple~CloudDocs")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def detect_google_drive_dir() -> Path | None:
    """
    Best-effort detection of a local folder synced by Google Drive for
    desktop. Google Drive for desktop can run in "Mirror files" mode
    (a real local folder, easiest to back up to) or "Stream files" mode
    (a virtual drive letter such as G:\\, which still behaves like a
    normal folder for file copies). Returns None if nothing is found -
    the administrator can browse to the right folder manually.
    """
    system = platform.system()
    home = Path.home()
    candidates: list[Path] = []
    if system == "Windows":
        import string
        # Stream mode: a dedicated drive letter, usually named "Google Drive".
        for letter in string.ascii_uppercase:
            drive_root = Path(f"{letter}:/")
            if (drive_root / "My Drive").is_dir():
                candidates.append(drive_root / "My Drive")
        # Mirror mode: a normal folder under the user's home directory.
        candidates += [
            home / "Google Drive" / "My Drive",
            home / "Google Drive",
        ]
    elif system == "Darwin":
        candidates += [
            Path("/Volumes/GoogleDrive/My Drive"),
            home / "Google Drive" / "My Drive",
        ]
        cloud_storage = home / "Library" / "CloudStorage"
        if cloud_storage.is_dir():
            for entry in cloud_storage.iterdir():
                if entry.name.startswith("GoogleDrive-") and (entry / "My Drive").is_dir():
                    candidates.append(entry / "My Drive")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def is_frozen() -> bool:
    """True when running as a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


def get_asset_path(relative: str) -> Path:
    """
    Resolve a bundled asset (e.g. logo) both in dev mode and when
    packaged by PyInstaller (which unpacks data files into sys._MEIPASS).
    """
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / relative


def get_logo_path() -> Path | None:
    """
    Locate the business logo. Search order:

    1. A logo the administrator imported through Settings -> Branding
       (copied into the per-user app-data folder, so it survives updates).
    2. A logo shipped next to the application in ``assets/``.

    Returns None when no logo has been provided yet - every caller must
    handle that and simply fall back to a text-only header.
    """
    for folder in (get_app_data_dir() / "branding", _assets_dir()):
        for name in LOGO_FILENAMES:
            candidate = folder / name
            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate
    return None


def get_branding_dir() -> Path:
    path = get_app_data_dir() / "branding"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _assets_dir() -> Path:
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets"
