# jwt-generate

Generate a signed HS256 JWT from the command line — entirely on your local machine.

## Why This Tool Exists

When building or debugging an API that validates JWTs, you often need a valid signed token quickly. The usual options are writing a one-off script, using an online generator, or spinning up the application just to mint a token. This script generates one locally using only the Python standard library — no third-party JWT libraries and nothing sent anywhere.

## Companion Tool

`jwt-generate` and `jwt-decode` are designed to work together. Generate a token here and immediately inspect it:

```bash
python jwt_generate.py --secret mysecret --out token.txt
python ../jwt-decode/jwt_decode.py --file token.txt --secret mysecret
```

## Requirements

No install needed — Python standard library only (`argparse`, `base64`, `json`, `time`, `hmac`, `hashlib`, `uuid`).

## Usage

```bash
# Minimal — generates an HS256 token with default claims
python jwt_generate.py --secret mysecretkey

# Custom expiry and role
python jwt_generate.py --secret mysecretkey --role viewer --exp-seconds 7200

# Add standard claims
python jwt_generate.py --secret mysecretkey --sub user_001 --iss myapp --aud api

# Add custom claims
python jwt_generate.py --secret mysecretkey --claim env=prod --claim version=2

# Add custom claims as JSON
python jwt_generate.py --secret mysecretkey --claims-json '{"env":"prod","tier":"free"}'

# Write token to a file
python jwt_generate.py --secret mysecretkey --out token.txt

# Pipe directly to jwt-decode
python jwt_generate.py --secret mysecretkey --no-newline | \
  xargs -I{} python ../jwt-decode/jwt_decode.py --token {} --secret mysecretkey
```

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--secret <key>` | Yes | — | HMAC signing secret |
| `--role <value>` | No | `admin` | Role claim value |
| `--exp-seconds <n>` | No | `3600` | Expiry in seconds from now |
| `--exp <unix>` | No | — | Explicit UNIX expiry timestamp (overrides `--exp-seconds`) |
| `--sub <value>` | No | — | Subject (`sub`) claim |
| `--iss <value>` | No | — | Issuer (`iss`) claim |
| `--aud <value>` | No | — | Audience (`aud`) claim |
| `--id <value>` | No | random UUID | Token ID claim |
| `--claim key=value` | No | — | Custom claim (repeatable) |
| `--claims-json <json>` | No | — | JSON string of additional claims |
| `--out <path>` | No | — | Write token to file (also prints to stdout) |
| `--no-newline` | No | off | Omit trailing newline — useful for piping |

## Default Claims

Every generated token includes:

| Claim | Value |
|---|---|
| `alg` | HS256 |
| `typ` | JWT |
| `role` | `admin` (override with `--role`) |
| `iat` | Current Unix timestamp |
| `exp` | `iat + 3600` (override with `--exp-seconds`) |
| `id` | Random UUID v4 (override with `--id`) |

## Windows path example

```bash
python jwt_generate.py --secret mysecretkey --out "C:\tokens\token.txt"
```

---

*Author: Mac | Version: 1.0.0 | Date: 2026-05-15*
