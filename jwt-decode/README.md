# jwt-decode

Decode and inspect a JWT (JSON Web Token) entirely on your local machine — no online tools, no third-party servers.

## Why This Tool Exists

The standard way to inspect a JWT is to paste it into [jwt.io](https://jwt.io) or a similar online tool. That means sending your token — which may contain user IDs, roles, session data, internal service names, and other sensitive claims — to a third-party server. This script decodes everything locally. Nothing leaves your machine.

## What It Shows

| Section | Details |
|---|---|
| **Header** | Algorithm (`alg`), token type (`typ`), and any other header fields |
| **Payload Claims** | All claims decoded and displayed. Timestamp claims (`exp`, `iat`, `nbf`) are shown as both Unix timestamps and human-readable UTC datetimes |
| **Expiry** | Whether the token is currently active or expired, with a human-readable duration (e.g. "Expires in 2 hrs, 14 min" or "EXPIRED 3 days ago") |
| **Signature** | VALID / INVALID / Not verified, depending on whether `--secret` was provided |

## Requirements

No install needed for console output or Markdown reports — the Python standard library covers everything.

`fpdf2` is only required if you use `--report pdf`:

```bash
pip install fpdf2
```

## Usage

```bash
# Decode and print to console
python jwt_decode.py --token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Read token from a file (keeps token out of shell history)
python jwt_decode.py --file path/to/token.txt

# Decode and verify the signature
python jwt_decode.py --token <jwt> --secret mysecretkey

# Save a Markdown report
python jwt_decode.py --token <jwt> --report md

# Save a PDF report
python jwt_decode.py --token <jwt> --report pdf

# Save both reports to a specific folder
python jwt_decode.py --token <jwt> --report md pdf --output-dir ./reports
```

## Arguments

| Argument | Required | Description |
|---|---|---|
| `--token <jwt>` | One of these two | JWT string pasted directly |
| `--file <path>` | One of these two | Path to a plain text file containing the JWT |
| `--secret <key>` | No | Secret key for HMAC signature verification |
| `--report [md] [pdf]` | No | Generate report file(s); omit for console output only |
| `--output-dir <path>` | No | Where to save report files (default: current directory) |

## Output Files

When `--report` is used, files are saved with a timestamp in the name:

```
jwt_decoded_YYYYMMDDHHmmss.md
jwt_decoded_YYYYMMDDHHmmss.pdf
```

The console summary is always printed regardless of whether `--report` is used.

## Signature Verification

Signature verification is supported natively for HMAC algorithms:

| Algorithm | Supported |
|---|---|
| HS256 | Yes |
| HS384 | Yes |
| HS512 | Yes |
| RS256 / RS512 | No — requires `pip install cryptography` |
| ES256 / ES512 | No — requires `pip install cryptography` |

For RS/ES algorithms the tool will still decode and display all claims correctly — it simply skips signature verification and notes why in the output.

## Why use `--file` instead of `--token`?

Anything passed as a command line argument can end up in your shell history (`.bash_history`, `.zsh_history`). If your JWT contains sensitive claims, using `--file` with a temporary text file is the safer option.

## Windows path example

```bash
python jwt_decode.py --file "C:/Users/Mac/tokens/token.txt"
python jwt_decode.py --token <jwt> --output-dir "C:/Users/Mac/reports"
```

## Testing

A set of pre-built test tokens and a step-by-step guide are included in the `test-tokens/` folder:

```
test-tokens/
  1_no_exp.txt           — HS256 token, no expiry claim
  2_active_with_exp.txt  — HS256 token, active expiry, array claims, iat/nbf/exp
  3_expired.txt          — HS256 token, expired 3 days ago
  4_hs384.txt            — HS384 token, active expiry
  5_rs256_asymmetric.txt — RS256 token (asymmetric, signature skipped)
  6_malformed.txt        — Broken token (only two parts)
  TESTING.md             — Exact commands and expected output for all 8 tests
```

The secret used to sign tokens 1–4 is `testsecret`. Open `TESTING.md` for the full test checklist.

---

*Author: Mac | Version: 1.1.0 | Date: 2026-05-17*
