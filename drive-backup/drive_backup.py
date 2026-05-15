# =============================================================================
# Tool:        drive-backup
# Author:      Mac
# Version:     1.0.0
# Date:        2026-05-14
# Repository:  https://github.com/mac/tools
#
# Description:
#   Copies a local directory tree to any mounted drive — Google Drive, OneDrive,
#   a NAS share, or a USB drive — using an incremental strategy: only new or
#   changed files are transferred, keeping run times short.
#
#   Configurable handling for files deleted from source:
#     untouched — destination is left as-is (default, nothing is removed)
#     delete    — files removed from source are permanently deleted from dest
#     markfile  — files removed from source are renamed with a "deleted-" prefix
#
# Why this tool exists:
#   A simple, local backup that requires no cloud account, no OAuth tokens, and
#   no third-party backup software. If your OS can mount the drive and assign it
#   a path, this tool can back up to it. Nothing is sent anywhere — the script
#   runs entirely on your machine.
#
# Required libraries (install before running):
#   pip install pyyaml
#
# Standard library modules used (no install needed):
#   os, sys, shutil, fnmatch, argparse, logging, pathlib, datetime, typing
#
# Configuration:
#   Edit config.yaml (in the same folder as this script) to set your source,
#   destination, ignore rules, and deletion behaviour.
#
#   Windows path example (forward slashes work and are easiest):
#     source_root:      "C:/Development"
#     destination_root: "G:/My Drive/Backup/Development"
#
#   Backslashes also work if quoted:
#     source_root:      "C:\\Development"
#     destination_root: "G:\\My Drive\\Backup\\Development"
#
# Usage:
#   python drive_backup.py                   # run using config.yaml
#   python drive_backup.py --dry-run         # simulate without writing anything
#   python drive_backup.py --config my.yaml  # use a different config file
#
# Output:
#   Progress and a summary are logged to console and optionally to a rotating
#   log file. Max file size is set via log_max_size_mb in config.yaml (default
#   10 MB). Two backup files are kept, so total max on disk is 3x that value.
#   The log file is automatically excluded from the backup.
# =============================================================================

import os
import sys
import shutil
import fnmatch
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set

import yaml


# =============================================================================
# Constants
# =============================================================================

DELETED_PREFIX          = "deleted-"
TIMESTAMP_TOLERANCE_SEC = 2   # absorbs FAT32 / NTFS timestamp rounding differences


# =============================================================================
# Config
# =============================================================================

def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        sys.exit(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_config(config: dict) -> None:
    """
    Validate required fields and known values.
    Prints all errors found and exits with a clear message.
    """
    errors = []

    if "source_root" not in config:
        errors.append("Missing required field: source_root")
    if "destination_root" not in config:
        errors.append("Missing required field: destination_root")

    # Detect the old field name and guide the user
    if "exclude_directories" in config and "exclude_top_level" not in config:
        errors.append(
            "'exclude_directories' has been renamed to 'exclude_top_level' — "
            "please update your config.yaml."
        )

    deleted = config.get("deleted_files", "untouched")
    valid_deleted = {"untouched", "delete", "markfile"}
    if deleted not in valid_deleted:
        errors.append(
            f"Invalid value for deleted_files: '{deleted}'. "
            f"Must be one of: {', '.join(sorted(valid_deleted))}"
        )

    log_max = config.get("log_max_size_mb", 10)
    if not isinstance(log_max, (int, float)) or log_max <= 0:
        errors.append(
            f"'log_max_size_mb' must be a positive number, got: {log_max!r}"
        )

    ignore = config.get("ignore", [])
    if not isinstance(ignore, list):
        errors.append(f"'ignore' must be a list, got: {type(ignore).__name__}")

    exclude = config.get("exclude_top_level", [])
    if exclude is not None and not isinstance(exclude, list):
        errors.append(
            f"'exclude_top_level' must be a list, got: {type(exclude).__name__}"
        )

    if errors:
        print("Configuration errors found:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


# =============================================================================
# Logging
# =============================================================================

def setup_logging(
    log_file: Optional[str],
    dry_run: bool,
    log_max_size_mb: float = 10,
) -> None:
    fmt     = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Rotate at log_max_size_mb; keep 2 backups so recent history is preserved.
        # Total max on disk: log_max_size_mb x 3 files.
        handlers.append(
            RotatingFileHandler(
                log_path,
                maxBytes=int(log_max_size_mb * 1024 * 1024),
                backupCount=2,
                encoding="utf-8",
            )
        )

    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)

    if dry_run:
        logging.info("=" * 60)
        logging.info("DRY RUN MODE — no files will be written or deleted")
        logging.info("=" * 60)


# =============================================================================
# Ignore logic
# =============================================================================

def is_ignored(name: str, rules: List[str]) -> bool:
    """
    Return True if `name` (a file or folder name, NOT a full path) matches
    any ignore rule.

    Rules support exact names (node_modules, .git) and glob patterns (*.log,
    .env.*). Applied at EVERY level of the directory tree.

    Note: this is different from exclude_top_level, which only applies to the
    first level of directories directly under source_root. Use ignore for
    things you want filtered everywhere (build artefacts, temp files, etc.)
    and exclude_top_level for entire project folders at the root level.
    """
    for rule in rules:
        if fnmatch.fnmatch(name, rule):
            return True
    return False


# =============================================================================
# Copy logic
# =============================================================================

def timestamps_differ(src: str, dst: str) -> bool:
    return abs(os.path.getmtime(src) - os.path.getmtime(dst)) > TIMESTAMP_TOLERANCE_SEC


def copy_directory(
    src_dir: Path,
    dst_dir: Path,
    ignore_rules: List[str],
    dry_run: bool,
    stats: Dict,
    log_file_abs: Optional[Path] = None,
) -> None:
    """
    Recursively copy src_dir into dst_dir, skipping unchanged files and any
    items matching ignore_rules. If log_file_abs is provided, that specific
    file is automatically skipped even if it falls inside src_dir.
    """
    for root, dirs, files in os.walk(src_dir, topdown=True):
        # Prune ignored directories in-place so os.walk won't descend into them
        pruned = []
        for d in dirs:
            if is_ignored(d, ignore_rules):
                logging.info(f"  [SKIP DIR ] {os.path.join(root, d)}")
                stats["dirs_skipped"] += 1
            else:
                pruned.append(d)
        dirs[:] = pruned

        rel_root = os.path.relpath(root, src_dir)
        dst_root = dst_dir / rel_root if rel_root != "." else dst_dir

        if not dry_run:
            dst_root.mkdir(parents=True, exist_ok=True)

        for filename in files:
            if is_ignored(filename, ignore_rules):
                logging.info(f"  [SKIP FILE] {os.path.join(root, filename)}")
                stats["files_skipped"] += 1
                continue

            src_file = Path(root) / filename

            # Auto-exclude the log file if it lives inside the source tree
            if log_file_abs and src_file.resolve() == log_file_abs:
                logging.info(f"  [AUTO-SKIP] {src_file} (log file)")
                continue

            dst_file = dst_root / filename

            if dst_file.exists() and not timestamps_differ(str(src_file), str(dst_file)):
                stats["files_unchanged"] += 1
                continue

            verb = "Would copy" if dry_run else "Copying  "
            logging.info(f"  [{verb}] {src_file}")

            if not dry_run:
                try:
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src_file), str(dst_file))
                    stats["files_copied"] += 1
                except Exception as exc:
                    logging.error(f"  [ERROR    ] {src_file} — {exc}")
                    stats["errors"] += 1
            else:
                stats["files_copied"] += 1


def copy_root_files(
    source_root: Path,
    destination_root: Path,
    ignore_rules: List[str],
    dry_run: bool,
    stats: Dict,
    log_file_abs: Optional[Path] = None,
) -> None:
    """
    Copy any files sitting directly in source_root (not inside a subdirectory).
    Previously these were silently skipped; they are now handled explicitly.
    """
    for item in sorted(source_root.iterdir()):
        if not item.is_file():
            continue
        if is_ignored(item.name, ignore_rules):
            logging.info(f"  [SKIP FILE] {item}")
            stats["files_skipped"] += 1
            continue
        if log_file_abs and item.resolve() == log_file_abs:
            logging.info(f"  [AUTO-SKIP] {item} (log file)")
            continue

        dst_file = destination_root / item.name

        if dst_file.exists() and not timestamps_differ(str(item), str(dst_file)):
            stats["files_unchanged"] += 1
            continue

        verb = "Would copy" if dry_run else "Copying  "
        logging.info(f"  [{verb}] {item}")

        if not dry_run:
            try:
                destination_root.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(item), str(dst_file))
                stats["files_copied"] += 1
            except Exception as exc:
                logging.error(f"  [ERROR    ] {item} — {exc}")
                stats["errors"] += 1
        else:
            stats["files_copied"] += 1


# =============================================================================
# Deletion sync logic
# =============================================================================

def _apply_deletion_action(
    path: Path,
    mode: str,
    dry_run: bool,
    stats: Dict,
    is_dir: bool,
) -> None:
    """Apply the configured deleted_files action to a single path."""
    if mode == "untouched":
        return

    if mode == "delete":
        logging.info(f"  [DELETED  ] {path}")
        if not dry_run:
            try:
                if is_dir:
                    shutil.rmtree(str(path))
                    stats["dirs_deleted"] += 1
                else:
                    path.unlink()
                    stats["files_deleted"] += 1
            except Exception as exc:
                logging.error(f"  [ERROR    ] Failed to delete {path} — {exc}")
                stats["errors"] += 1
        else:
            stats["dirs_deleted" if is_dir else "files_deleted"] += 1

    elif mode == "markfile":
        marked = path.parent / f"{DELETED_PREFIX}{path.name}"
        logging.info(f"  [MARKED   ] {path.name} -> {marked.name}")
        if not dry_run:
            try:
                path.rename(marked)
                stats["dirs_marked" if is_dir else "files_marked"] += 1
            except Exception as exc:
                logging.error(f"  [ERROR    ] Failed to mark {path} — {exc}")
                stats["errors"] += 1
        else:
            stats["dirs_marked" if is_dir else "files_marked"] += 1


def sync_deletions(
    src_dir: Path,
    dst_dir: Path,
    ignore_rules: List[str],
    deleted_files_mode: str,
    dry_run: bool,
    stats: Dict,
) -> None:
    """
    Scan dst_dir for files and folders that no longer exist in src_dir and
    apply the configured deleted_files action.

    Items already carrying the DELETED_PREFIX are left untouched — they were
    processed in a previous run and should not be re-marked or re-deleted.
    """
    if deleted_files_mode == "untouched" or not dst_dir.exists():
        return

    for root, dirs, files in os.walk(dst_dir, topdown=True):
        rel_root = Path(os.path.relpath(root, dst_dir))
        src_root = src_dir / rel_root if str(rel_root) != "." else src_dir

        # Evaluate each subdirectory
        keep_dirs = []
        for d in dirs:
            # Already marked or ignored — leave alone, do not descend
            if d.startswith(DELETED_PREFIX) or is_ignored(d, ignore_rules):
                continue
            src_subdir = src_root / d
            if not src_subdir.exists():
                # No longer in source — apply action and do not descend
                _apply_deletion_action(
                    Path(root) / d, deleted_files_mode, dry_run, stats, is_dir=True
                )
            else:
                keep_dirs.append(d)  # still present in source — descend
        dirs[:] = keep_dirs

        # Evaluate each file
        for filename in files:
            if filename.startswith(DELETED_PREFIX) or is_ignored(filename, ignore_rules):
                continue
            if not (src_root / filename).exists():
                _apply_deletion_action(
                    Path(root) / filename, deleted_files_mode, dry_run, stats, is_dir=False
                )


def sync_root_orphans(
    source_root: Path,
    destination_root: Path,
    exclude_top_level: Set[str],
    ignore_rules: List[str],
    deleted_files_mode: str,
    dry_run: bool,
    stats: Dict,
    log_file_abs: Optional[Path] = None,
) -> None:
    """
    Check for files and top-level directories in destination_root that no
    longer exist in source_root, and apply the configured deletion action.
    This covers the root level only — subdirectory orphans are handled by
    sync_deletions() called per directory.
    """
    if deleted_files_mode == "untouched" or not destination_root.exists():
        return

    for item in sorted(destination_root.iterdir()):
        if item.name.startswith(DELETED_PREFIX):
            continue

        if item.is_file():
            if is_ignored(item.name, ignore_rules):
                continue
            if log_file_abs and item.resolve() == log_file_abs:
                continue
            if not (source_root / item.name).exists():
                _apply_deletion_action(item, deleted_files_mode, dry_run, stats, is_dir=False)

        elif item.is_dir():
            if item.name in exclude_top_level or is_ignored(item.name, ignore_rules):
                continue
            if not (source_root / item.name).exists():
                _apply_deletion_action(item, deleted_files_mode, dry_run, stats, is_dir=True)


# =============================================================================
# Entry point
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Back up a local directory tree to any mounted drive."
    )
    parser.add_argument(
        "--config",
        default=Path(__file__).parent / "config.yaml",
        type=Path,
        help="Path to YAML config file (default: config.yaml next to this script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the backup without writing or deleting any files",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    validate_config(config)

    dry_run: bool           = args.dry_run or bool(config.get("dry_run", False))
    log_file: Optional[str] = config.get("log_file")
    log_max_size_mb: float  = config.get("log_max_size_mb", 10)
    deleted_files_mode: str = config.get("deleted_files", "untouched")

    setup_logging(log_file, dry_run, log_max_size_mb)

    source_root                  = Path(config["source_root"])
    destination_root             = Path(config["destination_root"])
    exclude_top_level: Set[str]  = set(config.get("exclude_top_level", []) or [])
    ignore_rules: List[str]      = config.get("ignore", []) or []

    # Resolve log file path so it can be auto-excluded from the backup
    log_file_abs: Optional[Path] = Path(log_file).resolve() if log_file else None

    # Validate source
    if not source_root.exists():
        logging.error(f"Source root not found: {source_root}")
        sys.exit(1)

    # Validate destination (skipped in dry-run so you can test without the drive mounted)
    if not dry_run and not destination_root.exists():
        logging.error(
            f"Destination root not accessible: {destination_root}\n"
            "Is the drive mounted and signed in?"
        )
        sys.exit(1)

    stats: Dict = {
        "files_copied":    0,
        "files_unchanged": 0,
        "files_skipped":   0,
        "dirs_skipped":    0,
        "files_deleted":   0,
        "dirs_deleted":    0,
        "files_marked":    0,
        "dirs_marked":     0,
        "errors":          0,
    }

    started = datetime.now()

    directories = sorted(
        d for d in source_root.iterdir()
        if d.is_dir() and d.name not in exclude_top_level
    )

    logging.info(f"Source         : {source_root}")
    logging.info(f"Destination    : {destination_root}")
    logging.info(f"Excluded (top) : {sorted(exclude_top_level) or '(none)'}")
    logging.info(f"Ignore rules   : {ignore_rules}")
    logging.info(f"Deleted files  : {deleted_files_mode}")
    logging.info(f"Log max size   : {log_max_size_mb} MB")
    logging.info(f"Directories    : {len(directories)} top-level to process")
    logging.info("-" * 60)

    # Copy files sitting directly in source_root
    root_files = [f for f in source_root.iterdir() if f.is_file()]
    if root_files:
        logging.info(f"Processing root-level files in: {source_root}")
        copy_root_files(
            source_root, destination_root, ignore_rules, dry_run, stats, log_file_abs
        )

    # Copy each top-level directory and sync its deletions
    for src_dir in directories:
        dst_dir = destination_root / src_dir.name
        logging.info(f"Processing: {src_dir}")
        copy_directory(src_dir, dst_dir, ignore_rules, dry_run, stats, log_file_abs)
        sync_deletions(src_dir, dst_dir, ignore_rules, deleted_files_mode, dry_run, stats)

    # Sync orphaned root-level files and directories
    sync_root_orphans(
        source_root, destination_root, exclude_top_level, ignore_rules,
        deleted_files_mode, dry_run, stats, log_file_abs
    )

    elapsed = datetime.now() - started
    logging.info("-" * 60)

    parts = [
        f"Done in {elapsed.total_seconds():.1f}s",
        f"{stats['files_copied']} copied",
        f"{stats['files_unchanged']} unchanged",
        f"{stats['files_skipped']} files skipped",
        f"{stats['dirs_skipped']} dirs skipped",
    ]
    if stats["files_deleted"] or stats["dirs_deleted"]:
        parts.append(
            f"{stats['files_deleted']} files deleted, {stats['dirs_deleted']} dirs deleted"
        )
    if stats["files_marked"] or stats["dirs_marked"]:
        parts.append(
            f"{stats['files_marked']} files marked, {stats['dirs_marked']} dirs marked"
        )
    parts.append(f"{stats['errors']} errors")
    logging.info(" - ".join(parts))

    if stats["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
