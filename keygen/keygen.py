# =============================================================================
# Tool:        keygen
# Author:      Mac
# Version:     1.0.0
# Date:        2026-05-15
# Repository:  https://github.com/mac/tools
#
# Description:
#   Generates cryptographically secure keys and tokens from the command line.
#   Supports multiple output types and is useful for generating API keys,
#   secrets, session tokens, and environment variable values.
#
# Why this tool exists:
#   Generating secure keys usually means either relying on an online generator
#   (which means trusting a third party with your secret) or writing a one-off
#   script each time. This tool runs entirely on your local machine and covers
#   the most common key formats with sensible defaults.
#
# Required libraries:
#   None — Python standard library only (secrets, base64, uuid, string)
#
# Usage:
#   python keygen.py
#   python keygen.py --type hex --length 64
#   python keygen.py --type base64url --length 43
#   python keygen.py --type api --length 32 --prefix prod
#   python keygen.py --type api --length 32 --group 4 --sep "-"
#   python keygen.py --count 5
#
# Windows path example:
#   python keygen.py --type api --length 64 --prefix prod
# =============================================================================

from __future__ import annotations

import argparse
import base64
import secrets
import string
import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KeyOptions:
    key_type: str = "api"
    length: int = 32
    prefix: Optional[str] = None
    group: int = 0
    sep: str = "-"
    alphabet: str = ""
    include_checksum: bool = False


DEFAULT_API_ALPHABET = string.ascii_letters + string.digits  # 62 chars


def _require_positive(n: int, name: str) -> None:
    if n <= 0:
        raise ValueError(f"{name} must be > 0")


def _base64url_no_pad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _group_string(s: str, group: int, sep: str) -> str:
    if group <= 0:
        return s
    return sep.join(s[i:i + group] for i in range(0, len(s), group))


def _simple_checksum_base36(s: str) -> str:
    """
    Lightweight checksum to catch typos (NOT a security feature).
    Produces 2 base36 characters.
    """
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    total = 0
    for ch in s:
        total = (total + ord(ch)) % (36 * 36)
    return alphabet[total // 36] + alphabet[total % 36]


def _gen_from_alphabet(length: int, alphabet: str) -> str:
    _require_positive(length, "length")
    if not alphabet:
        raise ValueError("alphabet must not be empty")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_key(opts: KeyOptions) -> str:
    kt = opts.key_type.lower().strip()
    _require_positive(opts.length, "length")

    if kt in ("api", "apikey", "alnum"):
        alphabet = opts.alphabet or DEFAULT_API_ALPHABET
        key = _gen_from_alphabet(opts.length, alphabet)

    elif kt == "hex":
        nbytes = (opts.length + 1) // 2
        key = secrets.token_hex(nbytes)[:opts.length]

    elif kt in ("base64url", "b64url"):
        nbytes = (opts.length * 3 + 3) // 4
        key = _base64url_no_pad(secrets.token_bytes(nbytes))
        if len(key) < opts.length:
            key += _base64url_no_pad(secrets.token_bytes(4))
        key = key[:opts.length]

    elif kt == "uuid":
        key = str(uuid.uuid4())
        key = (key.replace("-", "") if opts.length <= 32 else key)
        key = key[:opts.length] if opts.length < len(key) else key

    else:
        raise ValueError("Unknown type. Use: api | hex | base64url | uuid | alnum")

    if opts.group > 0:
        key = _group_string(key, opts.group, opts.sep)

    if opts.prefix:
        key = f"{opts.prefix}_{key}"

    if opts.include_checksum:
        compact = key.replace(opts.sep, "")
        key = f"{key}_{_simple_checksum_base36(compact)}"

    return key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate cryptographically secure keys and tokens locally.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python keygen.py
  python keygen.py --type hex --length 64
  python keygen.py --type base64url --length 43
  python keygen.py --type api --length 32 --prefix prod
  python keygen.py --type api --length 32 --group 4 --sep "-"
  python keygen.py --count 5

common use cases:
  NEXTAUTH_SECRET     python keygen.py --type base64url --length 43
  API key             python keygen.py --type api --length 32 --prefix sk
  Hex secret          python keygen.py --type hex --length 64
  UUID token          python keygen.py --type uuid
        """,
    )
    parser.add_argument("--type", dest="key_type", default="api",
                        metavar="TYPE",
                        help="api | hex | base64url | uuid | alnum  (default: api)")
    parser.add_argument("--length", type=int, default=32, metavar="N",
                        help="Key length in characters (default: 32)")
    parser.add_argument("--prefix", default=None, metavar="STR",
                        help="Optional prefix, e.g. 'prod' or 'sk'")
    parser.add_argument("--group", type=int, default=0, metavar="N",
                        help="Group key into blocks of N characters for readability")
    parser.add_argument("--sep", default="-", metavar="CHAR",
                        help="Separator used between groups (default: '-')")
    parser.add_argument("--alphabet", default="", metavar="CHARS",
                        help="Custom character set for api/alnum types")
    parser.add_argument("--checksum", action="store_true",
                        help="Append a 2-character checksum suffix for typo detection")
    parser.add_argument("--count", type=int, default=1, metavar="N",
                        help="Number of keys to generate (default: 1)")

    args = parser.parse_args()

    opts = KeyOptions(
        key_type=args.key_type,
        length=args.length,
        prefix=args.prefix,
        group=args.group,
        sep=args.sep,
        alphabet=args.alphabet,
        include_checksum=args.checksum,
    )

    for _ in range(args.count):
        print(generate_key(opts))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
