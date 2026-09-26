"""
Automatic off-computer backup (SRS-style requirement added by the
administrator: never lose data to a disk crash or a Windows reinstall).

Strategy: mirror the app's own data folder (database + uploaded
documents + photos + branding) into subfolders inside whatever cloud
sync folders the administrator has enabled - iCloud Drive and/or
Google Drive for desktop. Those desktop clients then take care of
actually getting the copy off this computer; this service's only job
is to keep a fresh, consistent copy sitting in the right local folder
for them to pick up.

The SQLite database is never copied with a plain file copy while the
app might be writing to it - sqlite3's built-in `backup()` API is used
instead, which safely snapshots a live database (see
https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup).
"""
from __future__ import annotations

import filecmp
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.config import (
    CLOUD_BACKUP_FOLDER_NAME,
    get_db_path,
    get_documents_storage_dir,
    get_photos_storage_dir,
    get_branding_dir,
    detect_icloud_drive_dir,
    detect_google_drive_dir,
)
from core.exceptions import BackupError
from core.logging_setup import get_logger
from infrastructure.repositories import SettingsRepository

logger = get_logger(__name__)

# Settings keys (stored in the same generic `settings` table as every
# other preference - no schema change needed).
KEY_ICLOUD_ENABLED = "backup_icloud_enabled"
KEY_ICLOUD_PATH = "backup_icloud_path"
KEY_ICLOUD_LAST = "backup_icloud_last_at"
KEY_ICLOUD_LAST_ERROR = "backup_icloud_last_error"
KEY_GDRIVE_ENABLED = "backup_gdrive_enabled"
KEY_GDRIVE_PATH = "backup_gdrive_path"
KEY_GDRIVE_LAST = "backup_gdrive_last_at"
KEY_GDRIVE_LAST_ERROR = "backup_gdrive_last_error"


@dataclass
class BackupDestinationConfig:
    key: str                 # "icloud" or "gdrive"
    label: str                # "iCloud Drive" / "Google Drive"
    enabled: bool
    path: str                 # administrator-chosen (or auto-detected) folder
    last_backup_at: str       # ISO timestamp, "" if never
    last_error: str           # "" if the last attempt succeeded


@dataclass
class BackupResult:
    key: str
    label: str
    success: bool
    message: str


class BackupService:
    """
    SRS-style note: this class only ever *writes into* the destination
    folders below `HaramaIn Backup/`; it never deletes or touches
    anything else the administrator keeps in their iCloud Drive or
    Google Drive, and it never modifies the live app database - it only
    reads from it via sqlite3's own safe backup() API.
    """

    def __init__(self):
        self.settings = SettingsRepository()

    # ------------------------------------------------------------ config
    def get_destinations(self) -> list[BackupDestinationConfig]:
        s = self.settings.get_all()
        icloud_default = detect_icloud_drive_dir()
        gdrive_default = detect_google_drive_dir()
        return [
            BackupDestinationConfig(
                key="icloud",
                label="iCloud Drive",
                enabled=s.get(KEY_ICLOUD_ENABLED, "0") == "1",
                path=s.get(KEY_ICLOUD_PATH, "") or (str(icloud_default) if icloud_default else ""),
                last_backup_at=s.get(KEY_ICLOUD_LAST, ""),
                last_error=s.get(KEY_ICLOUD_LAST_ERROR, ""),
            ),
            BackupDestinationConfig(
                key="gdrive",
                label="Google Drive",
                enabled=s.get(KEY_GDRIVE_ENABLED, "0") == "1",
                path=s.get(KEY_GDRIVE_PATH, "") or (str(gdrive_default) if gdrive_default else ""),
                last_backup_at=s.get(KEY_GDRIVE_LAST, ""),
                last_error=s.get(KEY_GDRIVE_LAST_ERROR, ""),
            ),
        ]

    def detect_default(self, key: str) -> Path | None:
        return detect_icloud_drive_dir() if key == "icloud" else detect_google_drive_dir()

    def save_destination(self, key: str, *, enabled: bool, path: str) -> None:
        if key not in ("icloud", "gdrive"):
            raise ValueError(f"Unknown backup destination: {key}")
        path = path.strip()
        if path:
            self._validate_local_folder(path)
        if key == "icloud":
            self.settings.set(KEY_ICLOUD_ENABLED, "1" if enabled else "0")
            self.settings.set(KEY_ICLOUD_PATH, path)
        else:
            self.settings.set(KEY_GDRIVE_ENABLED, "1" if enabled else "0")
            self.settings.set(KEY_GDRIVE_PATH, path)

    @staticmethod
    def _validate_local_folder(path: str) -> None:
        """
        Catches the single most common mistake here: pasting a Google
        Drive / iCloud *website* link (a URL you'd share with someone)
        instead of the local folder that the desktop sync app keeps on
        this computer. A URL is not a filesystem path the app can write
        into, so without this check it would silently create a
        meaningless local folder named after the URL and report
        "success" - the backup would never reach the real cloud folder.
        """
        if "://" in path:
            raise BackupError(
                "That looks like a web link (e.g. from \"Share\" in Google Drive or "
                "iCloud in a browser), not a folder on this computer. Install the "
                "desktop app (Google Drive for desktop / iCloud for Windows), sign in, "
                "then use Auto-Detect or Browse to pick the real local folder it syncs - "
                "usually named \"My Drive\" or \"iCloud Drive\"."
            )
        if not Path(path).is_absolute():
            raise BackupError(
                f'"{path}" is not a full folder path. Use Browse or Auto-Detect to pick '
                "the local folder your cloud sync app keeps on this computer."
            )

    # --------------------------------------------------------------- run
    def backup_now(self, only_enabled: bool = False) -> list[BackupResult]:
        """
        Back up to every destination that has a path set (or, with
        only_enabled=True, only the ones the administrator has switched
        on - used by the automatic/periodic backup so a path saved but
        left disabled is never silently used).
        """
        results: list[BackupResult] = []
        for dest in self.get_destinations():
            if not dest.path:
                continue
            if only_enabled and not dest.enabled:
                continue
            results.append(self._backup_to(dest))
        return results

    def _backup_to(self, dest: BackupDestinationConfig) -> BackupResult:
        try:
            self._validate_local_folder(dest.path)
        except BackupError as e:
            self._record_failure(dest.key, str(e))
            return BackupResult(dest.key, dest.label, False, str(e))
        target_root = Path(dest.path) / CLOUD_BACKUP_FOLDER_NAME
        try:
            target_root.mkdir(parents=True, exist_ok=True)
            self._backup_database(target_root / "harmain.db")
            self._mirror_dir(get_documents_storage_dir(), target_root / "documents")
            self._mirror_dir(get_photos_storage_dir(), target_root / "photos")
            self._mirror_dir(get_branding_dir(), target_root / "branding")
            stamp_file = target_root / "last_backup.txt"
            now = datetime.now().isoformat(timespec="seconds")
            stamp_file.write_text(
                f"Last backed up: {now}\nFrom computer: HaramaIn desktop app\n", encoding="utf-8"
            )
            self._record_success(dest.key, now)
            logger.info("Backup to %s succeeded (%s)", dest.label, target_root)
            return BackupResult(dest.key, dest.label, True, f"Backed up to {target_root}")
        except OSError as e:
            message = f"Could not write to {dest.path}: {e}"
            self._record_failure(dest.key, message)
            logger.error("Backup to %s failed: %s", dest.label, e)
            return BackupResult(dest.key, dest.label, False, message)
        except sqlite3.Error as e:
            message = f"Could not read the database for backup: {e}"
            self._record_failure(dest.key, message)
            logger.error("Backup to %s failed (db): %s", dest.label, e)
            return BackupResult(dest.key, dest.label, False, message)

    @staticmethod
    def _backup_database(dest_path: Path) -> None:
        """
        Safe snapshot of the live SQLite database via sqlite3.Connection.backup().

        The snapshot is built in a LOCAL temporary folder and only then copied as a plain
        file into the cloud folder. SQLite must never be run directly on a Google Drive /
        iCloud folder: those drives are virtual (Drive for desktop, "Stream" mode) and do
        not support the file locking and journal files SQLite needs, which is what caused
        "disk I/O error" on every backup.
        """
        from infrastructure.db import get_connection
        source = get_connection()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="haramain_backup_") as tmp_dir:
            snapshot = Path(tmp_dir) / "harmain.db"
            snapshot_conn = sqlite3.connect(str(snapshot))
            try:
                source.backup(snapshot_conn)
                snapshot_conn.commit()
            finally:
                snapshot_conn.close()
            BackupService._copy_file_to_cloud(snapshot, dest_path)

    @staticmethod
    def _copy_file_to_cloud(source: Path, dest_path: Path) -> None:
        """Copy one file into a cloud-sync folder: write a side file, then swap it in, so
        the sync app never uploads a half-written database. Falls back to a direct
        overwrite if the drive refuses the rename."""
        try:
            if dest_path.exists() and filecmp.cmp(source, dest_path, shallow=False):
                return                                   # nothing changed - do not re-upload
        except OSError:
            pass
        side = dest_path.with_name(dest_path.name + ".uploading")
        try:
            shutil.copyfile(source, side)
            try:
                os.replace(side, dest_path)
            except OSError:
                shutil.copyfile(source, dest_path)
                try:
                    side.unlink()
                except OSError:
                    pass
        except OSError:
            try:
                side.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _mirror_dir(source: Path, dest: Path) -> None:
        """Copy new or changed files only - the backup runs every minute, and re-writing every
        document and photo each time would keep Google Drive busy uploading the same files."""
        if not source.exists():
            return
        dest.mkdir(parents=True, exist_ok=True)
        for item in source.rglob("*"):
            target = dest / item.relative_to(source)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            try:
                if target.exists():
                    s, t = item.stat(), target.stat()
                    if s.st_size == t.st_size and s.st_mtime <= t.st_mtime + 2:
                        continue
            except OSError:
                pass
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

    # -------------------------------------------------------------- restore
    def restore_now(self, key: str) -> BackupResult:
        """
        The reverse of backup_now(): pulls the database + documents + photos
        + branding OUT of the chosen destination's "HaramaIn Backup" folder
        and overwrites this computer's live data with it - exactly what you
        need after reinstalling Windows/macOS or setting up a new machine,
        with no manual file copying.

        Uses sqlite3's own backup() API (in reverse) to write into the live,
        already-open database connection, so no other part of the app needs
        to close or reopen anything.
        """
        dest = next((d for d in self.get_destinations() if d.key == key), None)
        if not dest or not dest.path:
            message = "No folder is configured for this destination yet."
            return BackupResult(key, dest.label if dest else key, False, message)

        try:
            self._validate_local_folder(dest.path)
        except BackupError as e:
            return BackupResult(dest.key, dest.label, False, str(e))

        source_root = Path(dest.path) / CLOUD_BACKUP_FOLDER_NAME
        source_db = source_root / "harmain.db"
        if not source_db.exists():
            message = f"No backup found in {source_root} - nothing to restore."
            return BackupResult(dest.key, dest.label, False, message)

        try:
            self._restore_database(source_db)
            self._restore_dir(source_root / "documents", get_documents_storage_dir())
            self._restore_dir(source_root / "photos", get_photos_storage_dir())
            self._restore_dir(source_root / "branding", get_branding_dir())
            logger.info("Restore from %s succeeded (%s)", dest.label, source_root)
            return BackupResult(dest.key, dest.label, True, f"Restored from {source_root}")
        except OSError as e:
            message = f"Could not read from {dest.path}: {e}"
            logger.error("Restore from %s failed: %s", dest.label, e)
            return BackupResult(dest.key, dest.label, False, message)
        except sqlite3.Error as e:
            message = f"Could not restore the database: {e}"
            logger.error("Restore from %s failed (db): %s", dest.label, e)
            return BackupResult(dest.key, dest.label, False, message)

    @staticmethod
    def _restore_database(source_path: Path) -> None:
        """Copies the backed-up database INTO the live connection, overwriting
        every table's current content - the mirror image of _backup_database."""
        from infrastructure.db import get_connection, initialize_database
        dest_conn = get_connection()
        # Read the backup from a LOCAL copy - SQLite cannot be opened on a cloud drive.
        with tempfile.TemporaryDirectory(prefix="haramain_restore_") as tmp_dir:
            local_copy = Path(tmp_dir) / "harmain.db"
            shutil.copyfile(source_path, local_copy)
            source_conn = sqlite3.connect(str(local_copy))
            try:
                with dest_conn:
                    source_conn.backup(dest_conn)
            finally:
                source_conn.close()
        # A backup made by an older version may lack newer columns / numbering - bring it up to date.
        initialize_database()

    @staticmethod
    def _restore_dir(source: Path, dest: Path) -> None:
        if not source.exists():
            return
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, dest, dirs_exist_ok=True)

    def _record_success(self, key: str, when_iso: str) -> None:
        if key == "icloud":
            self.settings.set(KEY_ICLOUD_LAST, when_iso)
            self.settings.set(KEY_ICLOUD_LAST_ERROR, "")
        else:
            self.settings.set(KEY_GDRIVE_LAST, when_iso)
            self.settings.set(KEY_GDRIVE_LAST_ERROR, "")

    def _record_failure(self, key: str, message: str) -> None:
        if key == "icloud":
            self.settings.set(KEY_ICLOUD_LAST_ERROR, message)
        else:
            self.settings.set(KEY_GDRIVE_LAST_ERROR, message)
