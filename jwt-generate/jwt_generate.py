# =============================================================================
# Tool:        jwt-generate
# Author:      Mac
# Version:     1.0.0
# Date:        2026-05-15
# Repository:  https://github.com/mac/tools
#
# Description:
#   Generates a signed HS256 JWT from the command line. Useful for testing
#   APIs and services that require JWT authentication without needing a
#   running application or external library to mint tokens.
#
# Why this tool exists:
#   When building or debugging an API that validates JWTs, you often need a
#   valid signed token quickly. This script generates one locally using only
#   the Python standard library — no third-party JWT libraries required and
#   nothing is sent anywhere.
#
# Companion tool:
#   Use jwt-decode to inspect any token this tool generates:
#     python ../jwt-decode/jwt_decode.py --file token.txt --secret <your-secret>
#
# Required libraries:
#   None — Python standard library only (argparse, base64, json, time, hmac,
#          hashlib, uuid)
#
# Usage:
#   python jwt_generate.py --secret mysecretkey
#   python jwt_generate.py --secret mysecretkey --role admin --exp-seconds 7200
#   python jwt_generate.py --secret mysecretkey --sub user_001 --claim env=prod
#   python jwt_generate.py --secret mysecretkey --out token.txt
#
# Windows path example:
#   python jwt_generate.py --secret mysecretkey --out "C:\tokens\token.txt"
# =============================================================================

import argparse
import base64
import json
import time
import hmac
import hashlib
import uuid
from typing import Dict, Any, Optional
import sys


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def b64url_encode_json(obj: Any) -> str:
    data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return b64url_encode(data)


def sign_hs256(message: str, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return b64url_encode(sig)


def parse_claim_kv(pairs):
    claims = {}
    for item in pairs or []:
        if "=" not in item:
            raise ValueError(f"Invalid --claim '{item}'. Use key=value format.")
        k, v = item.split("=", 1)
        vl = v.lower()
        if vl == "true":
            claims[k] = True
        elif vl == "false":
            claims[k] = False
        elif vl in ("null", "none"):
            claims[k] = None
        else:
            try:
                claims[k] = int(v) if v.isdigit() else float(v) if "." in v else v
            except ValueError:
                claims[k] = v
    return claims


def create_jwt(
    secret: str,
    role: str = "admin",
    exp_seconds: int = 3600,
    subject: Optional[str] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    custom_claims: Optional[Dict[str, Any]] = None,
    explicit_exp: Optional[int] = None,
    token_id: Optional[str] = None,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "role": role,
        "iat": now,
        "exp": int(explicit_exp) if explicit_exp else now + int(exp_seconds),
        "id": token_id or str(uuid.uuid4()),
    }
    if subject:
        payload["sub"] = subject
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    if custom_claims:
        payload.update(custom_claims)

    header_b64  = b64url_encode_json(header)
    payload_b64 = b64url_encode_json(payload)
    message     = f"{header_b64}.{payload_b64}"
    signature   = sign_hs256(message, secret)
    return f"{message}.{signature}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate a signed HS256 JWT locally. Nothing leaves your machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python jwt_generate.py --secret mysecretkey
  python jwt_generate.py --secret mysecretkey --role admin --exp-seconds 7200
  python jwt_generate.py --secret mysecretkey --sub user_001 --iss myapp
  python jwt_generate.py --secret mysecretkey --claim env=prod --claim version=2
  python jwt_generate.py --secret mysecretkey --out token.txt

pipe to jwt-decode:
  python jwt_generate.py --secret mysecretkey --no-newline | \\
    xargs -I{} python ../jwt-decode/jwt_decode.py --token {} --secret mysecretkey
        """,
    )
    parser.add_argument("--secret",      required=True,             help="Signing secret (required)")
    parser.add_argument("--role",        default="admin",           help="Role claim value (default: admin)")
    parser.add_argument("--exp-seconds", type=int, default=3600,    help="Expiry in seconds from now (default: 3600)")
    parser.add_argument("--exp",         type=int,                  help="Explicit UNIX exp timestamp (overrides --exp-seconds)")
    parser.add_argument("--sub",                                    help="Subject (sub) claim")
    parser.add_argument("--iss",                                    help="Issuer (iss) claim")
    parser.add_argument("--aud",                                    help="Audience (aud) claim")
    parser.add_argument("--id",                                     help="Token ID claim (default: random UUID)")
    parser.add_argument("--claim",       action="append",           help="Custom claim as key=value (repeatable)")
    parser.add_argument("--claims-json",                            help='JSON string of additional claims e.g. \'{"env":"prod"}\'')
    parser.add_argument("--out",                                    help="Write token to file instead of stdout")
    parser.add_argument("--no-newline",  action="store_true",       help="Omit trailing newline (useful for piping)")

    args = parser.parse_args()

    try:
        extra_claims = parse_claim_kv(args.claim)
    except ValueError as e:
        parser.error(str(e))
    if args.claims_json:
        try:
            extra_claims.update(json.loads(args.claims_json))
        except json.JSONDecodeError as e:
            parser.error(f"Invalid --claims-json: {e}")

    token = create_jwt(
        secret=args.secret,
        role=args.role,
        exp_seconds=args.exp_seconds,
        subject=args.sub,
        issuer=args.iss,
        audience=args.aud,
        custom_claims=extra_claims,
        explicit_exp=args.exp,
        token_id=args.id,
    )

    print(token, end="" if args.no_newline else "\n")
    sys.stdout.flush()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(token + ("" if args.no_newline else "\n"))
        print(f"Token written to: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
