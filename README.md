# Tools

A collection of free, open-source utility scripts for developers.

Every tool in this repository runs entirely on your local machine — no data is sent to any external service, API, or AI model. This makes them safe to use with sensitive files such as environment configs, credentials, and internal data.

## Available Tools

| Tool | Description |
|---|---|
| [env-diff](./env-diff/) | Compare two `.env` files to identify duplicates, empty values, missing variables, and value mismatches. Generates a Markdown and PDF report. |
| [drive-backup](./drive-backup/) | Back up a local directory tree to any mounted drive (Google Drive, OneDrive, NAS, USB). Incremental copy with configurable handling for deleted files. |
| [jwt-decode](./jwt-decode/) | Decode and inspect a JWT entirely on your local machine. Shows all claims, expiry status, and optionally verifies HMAC signatures. Outputs to console, Markdown, or PDF. |

## Philosophy

Each tool in this repository:

- Runs entirely locally — nothing leaves your machine
- Has no hidden external dependencies or network calls
- Is self-contained in a single script where possible
- Includes clear setup and usage instructions in its own README
- Is free to use, fork, and adapt

## Adding More Tools

Each tool lives