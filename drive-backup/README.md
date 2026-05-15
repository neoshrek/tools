# drive-backup

Back up a local directory tree to any mounted drive — Google Drive, OneDrive, a NAS, or a USB drive — using an incremental copy strategy that only transfers new or changed files.

## Why This Tool Exists

Local backup tools usually require a cloud account, an OAuth login, or proprietary software. This script needs none of that. If your OS can mount the drive and assign it a path or letter, this tool can back up to it. Everything runs on your machine — nothing is uploaded via an API or sent anywhere.

## What It Does

- Copies only new or modified files (timestamp-based incremental — fast subsequent runs)
- Backs up files sitting directly in source root, not just subdirectories
- Configurable handling for files deleted from source (untouched, delete, or markfile)
- Skips build artefacts, version control folders, and other noise via ignore rules
- Auto-excludes the log file from the backup even if it lives inside source root
- Rotating log file (5 MB max per file, 3 backups kept — never grows unbounded)
- Supports `--dry-run` to simulate the entire backup before committing

## Requirements

Python 3.7 or higher.

Install the one required third-party library:

```bash
pip install pyyaml
```

All other dependencies are part of the Python standard library.

## Configuration

All settings live in `config.yaml` — no need to edit the Python file.

| Field | Required | Default | Description |
|---|---|---|---|
| `source_root` | Yes | — | Local directory to back up |
| `destination_root` | Yes | — | Mounted drive path to back up into |
| `exclude_top_level` | No | `[]` | Top-level folder names to skip entirely (see note below) |
| `deleted_files` | No | `untouched` | What to do when source files are deleted |
| `ignore` | No | `[]` | Glob patterns applied at every level of the tree |
| `log_file` | No | — | Path to log file; omit for console only |
| `log_max_size_mb` | No | `10` | Max size in MB before the log rotates (2 backups kept, total max 3x this value) |
| `dry_run` | No | `false` | Set `true` to simulate without writing |

### Windows path example

Forward slashes work on Windows and are easiest:

```yaml
source_root:      "C:/Development"
destination_root: "G:/My Drive/Backup/Development"
```

Backslashes also work if quoted:

```yaml
source_root:      "C:\\Development"
destination_root: "G:\\My Drive\\Backup\\Development"
```

### `exclude_top_level` vs `ignore`

These two settings have different scopes and are not interchangeable:

| Setting | Scope | Best used for |
|---|---|---|
| `exclude_top_level` | Top-level directories under `source_root` only | Skipping entire project folders by name (e.g. OldProjects, Sandbox) |
| `ignore` | Every file and folder at any depth in the tree | Build artefacts, temp files, `.git`, `node_modules`, `*.log` |

Example: adding `node_modules` to `exclude_top_level` would only skip a `node_modules` folder sitting directly in `source_root`. To skip it everywhere throughout the tree, add it to `ignore` instead — which is where it belongs.

### Deleted files modes

| Mode | Behaviour | Log tag |
|---|---|---|
| `untouched` | Destination is left as-is. Files removed from source are kept in the backup. **(default)** | — |
| `delete` | Files and folders removed from source are permanently deleted from the destination. | `[DELETED ]` |
| `markfile` | Files and folders removed from source are renamed with a `deleted-` prefix (e.g. `report.pdf` becomes `deleted-report.pdf`). They remain visible but are set aside and will not be re-processed on subsequent runs. | `[MARKED  ]` |

Always do a `--dry-run` before switching to `delete` mode for the first time.

## Usage

```bash
python drive_backup.py
```

With a different config file:

```bash
python drive_backup.py --config path/to/my_config.yaml
```

## Dry Run

Logs exactly what would be copied, skipped, deleted, or marked — without touching anything on disk:

```bash
python drive_backup.py --dry-run
```

Recommended before the first real run and before enabling `delete` mode.

## Output

Each run prints a summary line showing counts for every category:

```
2026-05-14 16:30:01 [INFO] Done in 4.2s — 12 copied — 384 unchanged — 7 files skipped — 3 dirs skipped — 2 files marked — 0 errors
```

Log tags used throughout the run:

| Tag | Meaning |
|---|---|
| `[Copying  ]` | File is being copied to destination |
| `[SKIP FILE]` | File matched an ignore rule |
| `[SKIP DIR ]` | Directory matched an ignore rule and was not descended into |
| `[AUTO-SKIP]` | Log file auto-excluded from backup |
| `[DELETED  ]` | File or folder deleted from destination (delete mode) |
| `[MARKED   ]` | File or folder renamed with `deleted-` prefix (markfile mode) |
| `[ERROR    ]` | A file operation failed (script exits with code 1 if any errors occur) |

---

*Author: Mac | Version: 1.0.0 | Date: 2026-05-14*
