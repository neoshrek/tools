# jwt-decode — Manual Test Guide

Run each test from the `jwt-decode/` folder. Every command, the expected output, and what is being verified is listed below.

The secret used to sign tokens 1–4 is: `testsecret`

---

## Test 1 — No expiry claim, no secret

**What it tests:** basic decode with `iat` but no `exp`; signature skipped when no secret provided; `--file` input works.

```bash
python jwt_decode.py --file test-tokens/1_no_exp.txt
```

**Expected output:**
- Header shows `alg: HS256`, `typ: JWT`
- Payload shows `sub`, `name`, and `iat` rendered as a human-readable UTC datetime
- No `EXPIRY` section (token has no `exp` claim)
- Signature line: `[SKIPPED] No --secret provided`

---

## Test 2 — Active token, valid signature, rich payload

**What it tests:** active expiry countdown; `iat`, `nbf`, `exp` all rendered as UTC datetimes; array claim displayed cleanly; valid HMAC signature.

```bash
python jwt_decode.py --file test-tokens/2_active_with_exp.txt --secret testsecret
```

**Expected output:**
- Payload shows `roles` as `admin, developer`
- `iat`, `nbf`, and `exp` all show Unix timestamp + human-readable UTC datetime
- Expiry section: `>> Expires in X hrs, Y min` (active)
- Signature: `[VALID  ] Signature is VALID`

---

## Test 2b — Wrong secret

**What it tests:** invalid HMAC signature when wrong secret is provided.

```bash
python jwt_decode.py --file test-tokens/2_active_with_exp.txt --secret wrongsecret
```

**Expected output:**
- Everything decodes normally (claims still visible)
- Signature: `[INVALID] Signature is INVALID`

---

## Test 3 — Expired token

**What it tests:** expired token detection and human-readable duration.

```bash
python jwt_decode.py --file test-tokens/3_expired.txt
```

**Expected output:**
- Expiry section: `!! EXPIRED 3 days ago`
- Signature: `[SKIPPED]` (no secret provided — expected)

---

## Test 4 — HS384 algorithm, valid signature

**What it tests:** HS384 (less common HMAC variant) is verified correctly; expiry countdown works.

```bash
python jwt_decode.py --file test-tokens/4_hs384.txt --secret testsecret
```

**Expected output:**
- Header shows `alg: HS384`
- Expiry section: `>> Expires in X min, Y sec` (active)
- Signature: `[VALID  ] Signature is VALID`

---

## Test 5 — RS256 asymmetric token

**What it tests:** asymmetric algorithm is decoded (claims visible) but signature verification is skipped with a clear explanation — not an error.

```bash
python jwt_decode.py --file test-tokens/5_rs256_asymmetric.txt --secret anysecret
```

**Expected output:**
- Header shows `alg: RS256`
- All claims decoded and displayed normally
- Signature: `[SKIPPED] Verification skipped — RS256 is not an HMAC algorithm...`

---

## Test 6 — Malformed token

**What it tests:** a broken token (only two parts instead of three) exits with a clear error message — no stack trace.

```bash
python jwt_decode.py --file test-tokens/6_malformed.txt
```

**Expected output:**
```
Error: Invalid JWT: expected 3 dot-separated parts, got 2.
```
Script exits with a non-zero exit code. No report files are created.

---

## Test 7 — Save Markdown and PDF reports

**What it tests:** `--report md pdf` creates both output files; `--output-dir` creates the folder if it does not exist.

```bash
python jwt_decode.py --file test-tokens/2_active_with_exp.txt --secret testsecret --report md pdf --output-dir ./reports
```

**Expected output:**
- Console output as normal
- Two lines at the bottom:
  ```
  Markdown report : reports/jwt_decoded_YYYYMMDDHHmmss.md
  PDF report      : reports/jwt_decoded_YYYYMMDDHHmmss.pdf
  ```
- Both files exist in the `reports/` folder

---

## Test 8 — Token passed via --token argument

**What it tests:** `--token` argument works as an alternative to `--file`; source line shows `--token argument` instead of a file path.

Copy the contents of `test-tokens/1_no_exp.txt` and paste it after `--token`:

```bash
python jwt_decode.py --token <paste token here>
```

**Expected output:**
- `Source  : --token argument` (not a file path)
- Same claims as Test 1

---

*All 8 tests passing = tool is working correctly.*
