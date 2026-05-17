# =============================================================================
# Tool:        jwt-decode
# Author:      Mac
# Version:     1.0.0
# Date:        2026-05-17
# Repository:  https://github.com/mac/tools
#
# Description:
#   Decodes a JWT (JSON Web Token) entirely on your local machine and displays
#   the header, payload claims, and expiry status in a readable format.
#   Optionally verifies the HMAC signature if a secret key is provided.
#
# Why this tool exists:
#   The standard way to inspect a JWT is to paste it into jwt.io or a similar
#   online tool — which sends your token (and any claims it contains: user IDs,
#   roles, session data, internal service names) to a third-party server.
#   This tool decodes everything locally. Nothing leaves your machine.
#
# Required libraries:
#   fpdf2 is only needed if --report pdf is used:
#     pip install fpdf2
#   All other functionality uses the Python standard library only —
#   no install needed for console output or --report md.
#
# Usage:
#   python jwt_decode.py --token <jwt>
#   python jwt_decode.py --file path/to/token.txt
#   python jwt_decode.py --token <jwt> --secret <key>
#   python jwt_decode.py --token <jwt> --report md
#   python jwt_decode.py --token <jwt> --report pdf
#   python jwt_decode.py --token <jwt> --report md pdf --output-dir ./reports
#
#   Windows path example (forward slashes or r"..." strings):
#     python jwt_decode.py --file "C:/Users/Mac/tokens/token.txt"
#     python jwt_decode.py --token <jwt> --output-dir "C:/Users/Mac/reports"
#
# Output:
#   Always prints a formatted summary to the console.
#   --report md  : also saves jwt_decoded_YYYYMMDDHHmmss.md
#   --report pdf : also saves jwt_decoded_YYYYMMDDHHmmss.pdf
#   --report md pdf : saves both
# =============================================================================

import os
import sys
import base64
import json
import hmac
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False


# =============================================================================
# JWT Decoding
# =============================================================================

def base64url_decode(data: str) -> bytes:
    """Decode a base64url string, adding the required padding automatically."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def decode_jwt(token: str) -> Tuple[Dict, Dict, str]:
    """
    Split and decode a JWT into its three components.
    Returns (header_dict, payload_dict, signature_b64url_string).
    Raises ValueError with a clear message on malformed input.
    """
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid JWT: expected 3 dot-separated parts, got {len(parts)}."
        )
    try:
        header = json.loads(base64url_decode(parts[0]))
    except Exception:
        raise ValueError("Invalid JWT: could not decode header (base64 or JSON error).")
    try:
        payload = json.loads(base64url_decode(parts[1]))
    except Exception:
        raise ValueError("Invalid JWT: could not decode payload (base64 or JSON error).")
    return header, payload, parts[2]


# =============================================================================
# Signature Verification
# =============================================================================

HMAC_ALGORITHMS: Dict[str, Any] = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}


def verify_signature(
    token: str, secret: str, algorithm: str
) -> Tuple[Optional[bool], str]:
    """
    Verify the JWT signature using the provided secret key.
    Returns (result, message):
      True  — signature is valid
      False — signature is invalid
      None  — verification not possible (unsupported algorithm)
    Only HMAC algorithms (HS256/HS384/HS512) are supported natively.
    RS256/ES256 and similar require the 'cryptography' library.
    """
    if algorithm not in HMAC_ALGORITHMS:
        return None, (
            f"Verification skipped — {algorithm} is not an HMAC algorithm. "
            "RS256/ES256 and similar asymmetric algorithms require the "
            "'cryptography' library (pip install cryptography)."
        )
    parts = token.strip().split(".")
    message = f"{parts[0]}.{parts[1]}".encode("utf-8")
    try:
        expected = base64url_decode(parts[2])
    except Exception:
        return False, "Could not decode the signature bytes."
    h = hmac.new(secret.encode("utf-8"), message, HMAC_ALGORITHMS[algorithm])
    valid = hmac.compare_digest(h.digest(), expected)
    if valid:
        return True, "Signature is VALID — token has not been tampered with."
    return False, (
        "Signature is INVALID — token may have been tampered with, "
        "or the wrong secret was provided."
    )


# =============================================================================
# Claim Formatting
# =============================================================================

TIMESTAMP_CLAIMS = {"exp", "iat", "nbf"}


def format_timestamp(ts: Any) -> str:
    """Convert a Unix timestamp to a readable UTC datetime string."""
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def expiry_info(exp: Any) -> Tuple[bool, str]:
    """Return (is_expired, human_readable_status) for an exp claim value."""
    try:
        exp_dt = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        total_sec = int((exp_dt - now).total_seconds())
        if total_sec < 0:
            return True, f"EXPIRED {_fmt_duration(-total_sec)} ago"
        return False, f"Expires in {_fmt_duration(total_sec)}"
    except Exception:
        return False, "Unable to parse expiry timestamp"


def _fmt_duration(seconds: int) -> str:
    """Return a human-readable duration string from a number of seconds."""
    days    = seconds // 86400
    hours   = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs    = seconds % 60
    if days >= 365:
        y = days // 365
        d = days % 365
        return f"{y} year{'s' if y != 1 else ''}" + (
            f", {d} day{'s' if d != 1 else ''}" if d else ""
        )
    if days > 0:
        return f"{days} day{'s' if days != 1 else ''}" + (
            f", {hours} hr{'s' if hours != 1 else ''}" if hours else ""
        )
    if hours > 0:
        return f"{hours} hr{'s' if hours != 1 else ''}" + (
            f", {minutes} min" if minutes else ""
        )
    if minutes > 0:
        return f"{minutes} min, {secs} sec"
    return f"{secs} second{'s' if secs != 1 else ''}"


def format_claim_value(key: str, value: Any) -> str:
    """Return a display-ready string for a claim value."""
    if key in TIMESTAMP_CLAIMS and isinstance(value, (int, float)):
        return f"{value}  ({format_timestamp(value)})"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


# =============================================================================
# Console Output
# =============================================================================

def print_report(
    header: Dict,
    payload: Dict,
    sig_result: Optional[bool],
    sig_message: str,
    token_source: str,
) -> None:
    """Print a formatted report to stdout."""
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = 60

    print()
    print("=" * width)
    print("  JWT Decoder")
    print(f"  Decoded : {now}")
    print(f"  Source  : {token_source}")
    print("=" * width)

    print()
    print("-- HEADER " + "-" * (width - 10))
    for k, v in header.items():
        print(f"  {k:<16} {v}")

    print()
    print("-- PAYLOAD " + "-" * (width - 11))
    for k, v in payload.items():
        print(f"  {k:<16} {format_claim_value(k, v)}")

    if "exp" in payload:
        is_expired, status = expiry_info(payload["exp"])
        print()
        print("-- EXPIRY " + "-" * (width - 10))
        tag = "  !! " if is_expired else "  >> "
        print(f"{tag}{status}")

    print()
    print("-- SIGNATURE " + "-" * (width - 13))
    if sig_result is True:
        print(f"  [VALID  ] {sig_message}")
    elif sig_result is False:
        print(f"  [INVALID] {sig_message}")
    else:
        print(f"  [SKIPPED] {sig_message}")

    print()
    print("=" * width)
    print()


# =============================================================================
# Markdown Report
# =============================================================================

def generate_markdown(
    header: Dict,
    payload: Dict,
    sig_result: Optional[bool],
    sig_message: str,
    token_source: str,
) -> str:
    """Return a markdown string for the full decode report."""
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("# JWT Decode Report\n")
    lines.append(f"**Decoded:** {now}  ")
    lines.append(f"**Source:** `{token_source}`  ")

    if "exp" in payload:
        is_expired, status = expiry_info(payload["exp"])
        badge = "EXPIRED" if is_expired else "ACTIVE"
        lines.append(f"**Expiry:** {badge} — {status}  ")

    if sig_result is True:
        lines.append("**Signature:** VALID  ")
    elif sig_result is False:
        lines.append("**Signature:** INVALID  ")
    else:
        lines.append("**Signature:** Not verified  ")

    # Header
    lines.append("\n---\n")
    lines.append("## Header\n")
    lines.append("| Claim | Value |")
    lines.append("|---|---|")
    for k, v in header.items():
        lines.append(f"| `{k}` | `{v}` |")

    # Payload
    lines.append("\n---\n")
    lines.append("## Payload Claims\n")
    lines.append("| Claim | Value |")
    lines.append("|---|---|")
    for k, v in payload.items():
        lines.append(f"| `{k}` | `{format_claim_value(k, v)}` |")

    # Expiry detail
    if "exp" in payload:
        is_expired, status = expiry_info(payload["exp"])
        lines.append("\n---\n")
        lines.append("## Expiry\n")
        lines.append(f"**Status:** {status}  ")
        lines.append(f"\n**Expiry timestamp:** `{format_timestamp(payload['exp'])}`  ")
        if "iat" in payload:
            lines.append(f"\n**Issued at:** `{format_timestamp(payload['iat'])}`  ")
        if "nbf" in payload:
            lines.append(f"\n**Not before:** `{format_timestamp(payload['nbf'])}`  ")

    # Signature
    lines.append("\n---\n")
    lines.append("## Signature Verification\n")
    if sig_result is True:
        lines.append(f"**Result:** VALID\n\n_{sig_message}_")
    elif sig_result is False:
        lines.append(f"**Result:** INVALID\n\n_{sig_message}_")
    else:
        lines.append(f"**Result:** Not verified\n\n_{sig_message}_")

    return "\n".join(lines)


# =============================================================================
# PDF Report
# =============================================================================

def generate_pdf(
    output_path: str,
    header: Dict,
    payload: Dict,
    sig_result: Optional[bool],
    sig_message: str,
    token_source: str,
) -> None:
    """Generate a PDF report using fpdf2."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_bg   = (44, 62, 80)
    header_text = (255, 255, 255)
    row_bg      = (236, 240, 241)
    green       = (39, 174, 96)
    red         = (192, 57, 43)

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "JWT Decode Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Decoded: {now}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Source: {token_source}", new_x="LMARGIN", new_y="NEXT")

    if "exp" in payload:
        is_expired, status = expiry_info(payload["exp"])
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*(red if is_expired else green))
        badge = "EXPIRED" if is_expired else "ACTIVE"
        pdf.cell(0, 6, f"Expiry: {badge} - {status}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    pdf.ln(4)

    def section_title(title: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(*header_bg)
        pdf.set_text_color(*header_text)
        pdf.cell(0, 8, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    def tbl_header(cols: List[str], widths: List[int]) -> None:
        pdf.set_fill_color(80, 100, 120)
        pdf.set_text_color(*header_text)
        pdf.set_font("Helvetica", "B", 9)
        for col, w in zip(cols, widths):
            pdf.cell(w, 7, col, border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

    def tbl_row(cols: List[str], widths: List[int], fill: bool = False) -> None:
        if fill:
            pdf.set_fill_color(*row_bg)
        pdf.set_font("Helvetica", "", 9)
        y0 = pdf.get_y()
        x0 = pdf.get_x()
        max_y = y0
        x = x0
        for col, w in zip(cols, widths):
            pdf.set_xy(x, y0)
            pdf.multi_cell(w, 6, str(col), border=1, fill=fill)
            max_y = max(max_y, pdf.get_y())
            x += w
        pdf.set_xy(x0, max_y)

    # Header section
    section_title("Header")
    tbl_header(["Claim", "Value"], [55, 130])
    for i, (k, v) in enumerate(header.items()):
        tbl_row([k, str(v)], [55, 130], fill=(i % 2 == 0))
    pdf.ln(4)

    # Payload section
    section_title("Payload Claims")
    tbl_header(["Claim", "Value"], [55, 130])
    for i, (k, v) in enumerate(payload.items()):
        tbl_row([k, format_claim_value(k, v)], [55, 130], fill=(i % 2 == 0))
    pdf.ln(4)

    # Expiry section
    if "exp" in payload:
        is_expired, status = expiry_info(payload["exp"])
        section_title("Expiry")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*(red if is_expired else green))
        pdf.cell(0, 7, status, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        rows = [("Expiry timestamp", format_timestamp(payload["exp"]))]
        if "iat" in payload:
            rows.append(("Issued at", format_timestamp(payload["iat"])))
        if "nbf" in payload:
            rows.append(("Not before", format_timestamp(payload["nbf"])))
        pdf.ln(2)
        tbl_header(["Field", "Value"], [55, 130])
        for i, (k, v) in enumerate(rows):
            tbl_row([k, v], [55, 130], fill=(i % 2 == 0))
        pdf.ln(4)

    # Signature section
    section_title("Signature Verification")
    if sig_result is True:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*green)
        pdf.cell(0, 7, "VALID", new_x="LMARGIN", new_y="NEXT")
    elif sig_result is False:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*red)
        pdf.cell(0, 7, "INVALID", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 7, "Not verified", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 6, sig_message.replace("—", "-"))

    pdf.output(output_path)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Decode and inspect a JWT token locally. Nothing leaves your machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python jwt_decode.py --token eyJhbGci...
  python jwt_decode.py --file token.txt
  python jwt_decode.py --token eyJhbGci... --secret mysecret
  python jwt_decode.py --token eyJhbGci... --report md
  python jwt_decode.py --token eyJhbGci... --report md pdf --output-dir ./reports
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--token", type=str,
        help="JWT token string pasted directly"
    )
    input_group.add_argument(
        "--file", type=str,
        help="Path to a plain text file containing the JWT (keeps token out of shell history)"
    )
    parser.add_argument(
        "--secret", type=str,
        help="Secret key for HMAC signature verification (HS256 / HS384 / HS512)"
    )
    parser.add_argument(
        "--report", nargs="+", choices=["md", "pdf"], metavar="FORMAT",
        help="Generate report file(s): md, pdf, or both. Omit for console output only."
    )
    parser.add_argument(
        "--output-dir", type=str, default=".",
        help="Directory for report files (default: current directory)"
    )

    args = parser.parse_args()

    # Validate PDF availability before doing any work
    report_formats: List[str] = list(dict.fromkeys(args.report or []))
    if "pdf" in report_formats and not FPDF_AVAILABLE:
        sys.exit(
            "Error: fpdf2 is required for PDF output.\n"
            "  Install it with: pip install fpdf2"
        )

    # Read token
    if args.token:
        token        = args.token.strip()
        token_source = "--token argument"
    else:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.exit(f"Error: File not found: {args.file}")
        token        = file_path.read_text(encoding="utf-8").strip()
        token_source = str(file_path)

    if not token:
        sys.exit("Error: Token is empty.")

    # Decode
    try:
        header, payload, _ = decode_jwt(token)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")

    # Verify signature
    sig_result: Optional[bool] = None
    if args.secret:
        algorithm = header.get("alg", "")
        sig_result, sig_message = verify_signature(token, args.secret, algorithm)
    else:
        sig_message = (
            "No --secret provided. "
            "Pass --secret <key> to verify the signature."
        )

    # Always print to console
    print_report(header, payload, sig_result, sig_message, token_source)

    # Optional file reports
    if report_formats:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        base_name = f"jwt_decoded_{timestamp}"

        if "md" in report_formats:
            md_path = output_dir / f"{base_name}.md"
            md_path.write_text(
                generate_markdown(header, payload, sig_result, sig_message, token_source),
                encoding="utf-8",
            )
            print(f"Markdown report : {md_path}")

        if "pdf" in report_formats:
            pdf_path = output_dir / f"{base_name}.pdf"
            generate_pdf(
                str(pdf_path), header, payload, sig_result, sig_message, token_source
            )
            print(f"PDF report      : {pdf_path}")


if __name__ == "__main__":
    main()
