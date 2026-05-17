# env-diff

Compare two `.env` files locally and generate a detailed Markdown and PDF report.

## Why This Tool Exists

Comparing `.env` files often means copying their contents into an LLM prompt or an online diff tool — which risks exposing API keys, database passwords, JWT secrets, and other sensitive credentials. This script runs entirely on your machine. Nothing leaves your computer.

## What It Checks

| Check | Description |
|---|---|
| **Duplicates** | Variables defined more than once within a single file |
| **Empty values** | Variables present but with no value assigned (`MYVAR=`) |
| **Missing variables** | Variables present in one file but absent from the other |
| **Value mismatches** | Variables present in both files but with different values |
| **Malformed lines** | Lines with no `=` sign that could not be parsed |

## Requirements

- Python 3.7 or higher

Install the one required third-party library:

```bash
pip install fpdf2
```

All other dependencies (`argparse`, `os`, `datetime`, `pathlib`, `collections`) are part of the Python standard library — no additional installs needed.

## Usage

Pass the two files to compare as arguments. An output directory is optional — reports are saved to the current directory by default.

```bash
# Basic comparison — reports saved to current directory
python env_diff.py --file1 .env.staging --file2 .env.production

# Save reports to a specific folder
python env_diff.py --file1 .env.staging --file2 .env.production --output-dir ./reports
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--file1 <path>` | Yes | Path to the first `.env` file |
| `--file2 <path>` | Yes | Path to the second `.env` file |
| `--output-dir <path>` | No | Directory to save reports (default: current directory) |

### Windows examples

```bash
python env_diff.py --file1 "C:\projects\myapp\.env.staging" ^
                   --file2 "C:\projects\myapp\.env.production"

python env_diff.py --file1 "C:\projects\myapp\.env.staging" ^
                   --file2 "C:\projects\myapp\.env.production" ^
                   --output-dir "C:\projects\myapp\reports"
```

## Output

Two report files are written to `--output-dir`, both named with a timestamp:

```
env_compared_YYYYMMDDHHmmss.md
env_compared_YYYYMMDDHHmmss.pdf
```

Each report contains the following sections:

| Section | Description |
|---|---|
| Summary | Count of all findings at a glance |
| Duplicates | Variables declared more than once, listed per file |
| Empty Values | Variables with no assigned value, listed per file |
| Missing Variables | Variables absent from one file but present in the other |
| Value Mismatches | Variables in both files with differing values |
| Malformed Lines | Lines that could not be parsed |
| Matching Variables | Variables identical in both files |

## Parsing Rules

- Lines starting with `#` are treated as comments and skipped
- Blank lines are skipped
- Variables and values are split on the **first** `=` sign only — values containing `=` characters are handled correctly (e.g. `SECRET=abc==base64` → variable: `SECRET`, value: `abc==base64`)
- Surrounding quotes are stripped from values (both `"` and `'`)
- Lines with no `=` sign are flagged as malformed in the report rather than silently dropped

---

*Author: Mac | Version: 1.1.0 | Date: 2026-05-17*
