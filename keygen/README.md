# keygen

Generate cryptographically secure keys and tokens entirely on your local machine.

## Why This Tool Exists

Generating secrets usually means either trusting an online generator (which means sending a request to a third-party server) or writing a one-off script each time. This tool runs entirely locally, covers the most common key formats, and works without any external dependencies.

## What It Generates

| Type | Description | Example use |
|---|---|---|
| `api` | URL-safe alphanumeric (A-Z, a-z, 0-9) | API keys, session tokens |
| `hex` | Lowercase hexadecimal | Signing secrets, HMAC keys |
| `base64url` | URL-safe Base64 (no padding) | `NEXTAUTH_SECRET`, JWT secrets |
| `uuid` | UUID v4 | Database IDs, request IDs |
| `alnum` | Alias for `api` | Same as api |

## Requirements

No install needed — Python standard library only (`secrets`, `base64`, `uuid`, `string`).

## Usage

```bash
# Default: 32-character alphanumeric API key
python keygen.py

# Specific type and length
python keygen.py --type hex --length 64
python keygen.py --type base64url --length 43
python keygen.py --type uuid

# Add a prefix (useful for identifying key type at a glance)
python keygen.py --type api --length 32 --prefix sk
python keygen.py --type api --length 32 --prefix prod

# Group characters for readability
python keygen.py --type api --length 32 --group 8
python keygen.py --type api --length 32 --group 4 --sep "_"

# Generate multiple keys at once
python keygen.py --count 5

# Add a checksum suffix for typo detection (not a security feature)
python keygen.py --type api --length 32 --checksum
```

## Arguments

| Argument | Default | Description |
|---|---|---|
| `--type` | `api` | Key type: `api`, `hex`, `base64url`, `uuid`, `alnum` |
| `--length` | `32` | Key length in characters |
| `--prefix` | — | Prefix string, e.g. `sk`, `prod`. Appended as `prefix_key` |
| `--group` | `0` | Group characters into blocks of N for readability |
| `--sep` | `-` | Separator between groups (default: `-`) |
| `--alphabet` | — | Custom character set for `api` / `alnum` types |
| `--checksum` | off | Append 2-character checksum suffix for typo detection |
| `--count` | `1` | Number of keys to generate |

## Common Use Cases

```bash
# NEXTAUTH_SECRET
python keygen.py --type base64url --length 43

# Stripe-style API key
python keygen.py --type api --length 32 --prefix sk

# Hex HMAC signing secret
python keygen.py --type hex --length 64

# Grouped key for readability (e.g. activation codes)
python keygen.py --type api --length 24 --group 6 --sep "-"

# Batch of unique IDs
python keygen.py --type uuid --count 10
```

## Security Notes

All randomness comes from Python's `secrets` module, which uses the operating system's cryptographically secure random number generator. This is appropriate for generating production secrets.

The `--checksum` flag appends a 2-character suffix for typo detection only — it is not a security feature and does not add cryptographic strength.

---

*Author: Mac | Version: 1.0.0 | Date: 2026-05-17*
