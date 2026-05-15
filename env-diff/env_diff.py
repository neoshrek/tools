# =============================================================================
# Tool:        env-diff
# Author:      Mac
# Version:     1.1.0
# Date:        2026-05-15
# Repository:  https://github.com/mac/tools
#
# Description:
#   Compares two .env files and generates a detailed report highlighting:
#     - Duplicate variables (a variable declared more than once in one file)
#     - Empty values (variables present but with no value assigned)
#     - Missing variables (present in one file but absent from the other)
#     - Value mismatches (present in both files but with different values)
#     - Malformed lines (lines with no = sign that cannot be parsed)
#
# Why this tool exists:
#   Comparing .env files often means copying their contents into an LLM or
#   an online diff tool, which risks exposing API keys, database passwords,
#   JWT secrets, and other sensitive credentials. This script runs entirely
#   on your local machine — nothing is sent anywhere.
#
# Required libraries (install before running):
#   pip install fpdf2
#
# Standard library modules used (no install needed):
#   argparse, os, datetime, pathlib, collections
#
# Usage:
#   python env_diff.py --file1 .env.staging --file2 .env.production
#   python env_diff.py --file1 .env.staging --file2 .env.production --output-dir ./reports
#
# Windows path example:
#   python env_diff.py --file1 "C:\projects\myapp\.env.staging" ^
#                      --file2 "C:\projects\myapp\.env.production" ^
#                      --output-dir "C:\projects\myapp\reports"
#
# Output:
#   Two timestamped report files written to --output-dir (default: current directory):
#     env_compared_YYYYMMDDHHmmss.md
#     env_compared_YYYYMMDDHHmmss.pdf
# =============================================================================

import argparse
import os
from datetime import datetime
from pathlib import Path
from collections import Counter
from fpdf import FPDF


def parse_env_file(filepath):
    """
    Parse an env file and return a tuple of:
      rows       — list of (variable, value) tuples, sorted alphabetically
      duplicates — list of variable names that appear more than once
      empty      — list of variable names whose value is an empty string
      malformed  — list of line descriptions that could not be parsed

    Parsing rules:
      - Blank lines are skipped
      - Lines starting with # are treated as comments and skipped
      - Split is performed on the FIRST = sign only
      - Surrounding quotes (" or ') are stripped from values
      - Lines with no = sign are recorded as malformed
    """
    raw_entries = []
    malformed   = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" not in line:
                malformed.append(f"Line {line_num}: {line}")
                continue

            variable, value = line.split("=", 1)
            variable = variable.strip()
            value    = value.strip()

            # Strip surrounding quotes
            if len(value) >= 2:
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]

            raw_entries.append((variable, value))

    var_counts = Counter(var for var, _ in raw_entries)
    duplicates = sorted([var for var, count in var_counts.items() if count > 1])
    empty      = sorted([var for var, val in raw_entries if val == ""])
    rows       = sorted(raw_entries, key=lambda x: x[0].lower())

    return rows, duplicates, empty, malformed


def compare_files(rows1, rows2):
    """
    Compare two parsed env file row sets and return:
      only_in_1        — variables only present in file 1
      only_in_2        — variables only present in file 2
      value_mismatches — list of (variable, value_in_1, value_in_2) tuples
      matching         — list of variable names identical in both files
      dict1, dict2     — dicts of variable->value (first occurrence used)
    """
    dict1 = {}
    for var, val in rows1:
        if var not in dict1:
            dict1[var] = val

    dict2 = {}
    for var, val in rows2:
        if var not in dict2:
            dict2[var] = val

    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())

    only_in_1 = sorted(keys1 - keys2)
    only_in_2 = sorted(keys2 - keys1)

    value_mismatches = []
    matching         = []

    for key in sorted(keys1 & keys2):
        if dict1[key] != dict2[key]:
            value_mismatches.append((key, dict1[key], dict2[key]))
        else:
            matching.append(key)

    return only_in_1, only_in_2, value_mismatches, matching, dict1, dict2


# =============================================================================
# MARKDOWN REPORT
# =============================================================================

def generate_markdown(file1_name, file2_name,
                      rows1, dups1, empty1, malformed1,
                      rows2, dups2, empty2, malformed2,
                      only_in_1, only_in_2, value_mismatches, matching):
    """Return a markdown string for the full comparison report."""

    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("# ENV File Comparison Report\n")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**File 1:** `{file1_name}`  ")
    lines.append(f"**File 2:** `{file2_name}`  ")

    # --- Summary ---
    lines.append("\n---\n")
    lines.append("## Summary\n")
    lines.append("| Category | Count |")
    lines.append("|---|---|")
    lines.append(f"| Total variables in File 1 | {len(rows1)} |")
    lines.append(f"| Total variables in File 2 | {len(rows2)} |")
    lines.append(f"| Duplicates in File 1 | {len(dups1)} |")
    lines.append(f"| Duplicates in File 2 | {len(dups2)} |")
    lines.append(f"| Empty values in File 1 | {len(empty1)} |")
    lines.append(f"| Empty values in File 2 | {len(empty2)} |")
    lines.append(f"| Missing from File 2 | {len(only_in_1)} |")
    lines.append(f"| Missing from File 1 | {len(only_in_2)} |")
    lines.append(f"| Value mismatches | {len(value_mismatches)} |")
    lines.append(f"| Matching variables | {len(matching)} |")

    # --- Duplicates ---
    lines.append("\n---\n")
    lines.append("## Duplicates\n")
    lines.append(f"### File 1: `{file1_name}`\n")
    if dups1:
        lines.append("| Variable |")
        lines.append("|---|")
        for var in dups1:
            lines.append(f"| `{var}` |")
    else:
        lines.append("_No duplicates found._")

    lines.append(f"\n### File 2: `{file2_name}`\n")
    if dups2:
        lines.append("| Variable |")
        lines.append("|---|")
        for var in dups2:
            lines.append(f"| `{var}` |")
    else:
        lines.append("_No duplicates found._")

    # --- Empty Values ---
    lines.append("\n---\n")
    lines.append("## Empty Values\n")
    lines.append(f"### File 1: `{file1_name}`\n")
    if empty1:
        lines.append("| Variable |")
        lines.append("|---|")
        for var in empty1:
            lines.append(f"| `{var}` |")
    else:
        lines.append("_No empty values found._")

    lines.append(f"\n### File 2: `{file2_name}`\n")
    if empty2:
        lines.append("| Variable |")
        lines.append("|---|")
        for var in empty2:
            lines.append(f"| `{var}` |")
    else:
        lines.append("_No empty values found._")

    # --- Missing Variables ---
    lines.append("\n---\n")
    lines.append("## Missing Variables\n")
    lines.append(f"### Missing from File 2: `{file2_name}`\n")
    if only_in_1:
        lines.append("| Variable |")
        lines.append("|---|")
        for var in only_in_1:
            lines.append(f"| `{var}` |")
    else:
        lines.append("_No variables missing from File 2._")

    lines.append(f"\n### Missing from File 1: `{file1_name}`\n")
    if only_in_2:
        lines.append("| Variable |")
        lines.append("|---|")
        for var in only_in_2:
            lines.append(f"| `{var}` |")
    else:
        lines.append("_No variables missing from File 1._")

    # --- Value Mismatches ---
    lines.append("\n---\n")
    lines.append("## Value Mismatches\n")
    lines.append("_Variables present in both files but with different values._\n")
    if value_mismatches:
        lines.append("| Variable | File 1 Value | File 2 Value |")
        lines.append("|---|---|---|")
        for var, val1, val2 in value_mismatches:
            lines.append(f"| `{var}` | `{val1}` | `{val2}` |")
    else:
        lines.append("_No value mismatches found._")

    # --- Malformed Lines ---
    lines.append("\n---\n")
    lines.append("## Malformed Lines\n")
    lines.append("_Lines that could not be parsed (no `=` sign found)._\n")
    lines.append(f"### File 1: `{file1_name}`\n")
    if malformed1:
        lines.append("| Line |")
        lines.append("|---|")
        for entry in malformed1:
            lines.append(f"| `{entry}` |")
    else:
        lines.append("_No malformed lines found._")

    lines.append(f"\n### File 2: `{file2_name}`\n")
    if malformed2:
        lines.append("| Line |")
        lines.append("|---|")
        for entry in malformed2:
            lines.append(f"| `{entry}` |")
    else:
        lines.append("_No malformed lines found._")

    # --- Matching Variables ---
    lines.append("\n---\n")
    lines.append("## Matching Variables\n")
    lines.append("_Variables present in both files with identical values._\n")
    if matching:
        lines.append("| Variable |")
        lines.append("|---|")
        for var in matching:
            lines.append(f"| `{var}` |")
    else:
        lines.append("_No matching variables found._")

    return "\n".join(lines)


# =============================================================================
# PDF REPORT
# =============================================================================

def generate_pdf(output_path, file1_name, file2_name,
                 rows1, dups1, empty1, malformed1,
                 rows2, dups2, empty2, malformed2,
                 only_in_1, only_in_2, value_mismatches, matching):
    """Generate a PDF report using fpdf2."""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Title ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ENV File Comparison Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated: {now}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"File 1: {file1_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"File 2: {file2_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Helper: section heading
    def section_title(title):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(52, 73, 94)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 8, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # Helper: sub-section heading
    def sub_title(title):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(189, 195, 199)
        pdf.cell(0, 7, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(1)

    # Helper: table row (fixed height — for short single-line content)
    def table_row(cols, widths, bold=False, fill=False, fill_rgb=(245, 245, 245)):
        if fill:
            pdf.set_fill_color(*fill_rgb)
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        for col, width in zip(cols, widths):
            text = str(col)
            if len(text) > 60:
                text = text[:57] + "..."
            pdf.cell(width, 7, text, border=1, fill=fill)
        pdf.ln()

    # Helper: wrapping table row — all cells in a row share the same height.
    # Step 1: pre-calculate the wrapped line count for every cell.
    # Step 2: draw each cell box (rect) at the uniform row height.
    # Step 3: write the text over the box without a border.
    def wrapping_table_row(cols, widths, fill=False, fill_rgb=(245, 245, 245)):
        line_h = 6
        pdf.set_font("Helvetica", "", 9)

        # Pre-calculate lines needed per cell (split_only does not render anything)
        lines_per_cell = [
            len(pdf.multi_cell(w, line_h, str(col), dry_run=True, output="LINES", wrapmode="CHAR"))
            for col, w in zip(cols, widths)
        ]
        max_lines = max(lines_per_cell) if lines_per_cell else 1
        row_h = max_lines * line_h

        x0 = pdf.get_x()
        y0 = pdf.get_y()
        x = x0

        for col, width in zip(cols, widths):
            # Draw uniform-height box
            if fill:
                pdf.set_fill_color(*fill_rgb)
            pdf.rect(x, y0, width, row_h, style="FD" if fill else "D")
            # Write text inside (no border, no fill — already drawn above)
            pdf.set_xy(x, y0)
            pdf.multi_cell(width, line_h, str(col), border=0, fill=False, wrapmode="CHAR")
            x += width

        pdf.set_xy(x0, y0 + row_h)

    # Helper: italic message
    def note(msg):
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, msg, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    header_rgb  = (44, 62, 80)
    header_text = (255, 255, 255)
    alt_rgb     = (236, 240, 241)

    def table_header(cols, widths):
        pdf.set_fill_color(*header_rgb)
        pdf.set_text_color(*header_text)
        pdf.set_font("Helvetica", "B", 9)
        for col, width in zip(cols, widths):
            pdf.cell(width, 7, col, border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

    # --- Summary ---
    section_title("Summary")
    summary_data = [
        ("Total variables in File 1", len(rows1)),
        ("Total variables in File 2", len(rows2)),
        ("Duplicates in File 1",      len(dups1)),
        ("Duplicates in File 2",      len(dups2)),
        ("Empty values in File 1",    len(empty1)),
        ("Empty values in File 2",    len(empty2)),
        ("Missing from File 2",       len(only_in_1)),
        ("Missing from File 1",       len(only_in_2)),
        ("Value mismatches",          len(value_mismatches)),
        ("Matching variables",        len(matching)),
    ]
    table_header(["Category", "Count"], [155, 30])
    for i, (label, count) in enumerate(summary_data):
        table_row([label, count], [155, 30], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    pdf.ln(4)

    # --- Duplicates ---
    section_title("Duplicates")
    sub_title(f"File 1: {file1_name}")
    if dups1:
        table_header(["Variable"], [185])
        for i, var in enumerate(dups1):
            table_row([var], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No duplicates found.")

    pdf.ln(2)
    sub_title(f"File 2: {file2_name}")
    if dups2:
        table_header(["Variable"], [185])
        for i, var in enumerate(dups2):
            table_row([var], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No duplicates found.")
    pdf.ln(4)

    # --- Empty Values ---
    section_title("Empty Values")
    sub_title(f"File 1: {file1_name}")
    if empty1:
        table_header(["Variable"], [185])
        for i, var in enumerate(empty1):
            table_row([var], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No empty values found.")

    pdf.ln(2)
    sub_title(f"File 2: {file2_name}")
    if empty2:
        table_header(["Variable"], [185])
        for i, var in enumerate(empty2):
            table_row([var], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No empty values found.")
    pdf.ln(4)

    # --- Missing Variables ---
    section_title("Missing Variables")
    sub_title(f"Missing from File 2: {file2_name}")
    if only_in_1:
        table_header(["Variable"], [185])
        for i, var in enumerate(only_in_1):
            table_row([var], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No variables missing from File 2.")

    pdf.ln(2)
    sub_title(f"Missing from File 1: {file1_name}")
    if only_in_2:
        table_header(["Variable"], [185])
        for i, var in enumerate(only_in_2):
            table_row([var], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No variables missing from File 1.")
    pdf.ln(4)

    # --- Value Mismatches ---
    section_title("Value Mismatches")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, "Variables present in both files but with different values.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    if value_mismatches:
        table_header(["Variable", "File 1 Value", "File 2 Value"], [60, 62, 63])
        for i, (var, val1, val2) in enumerate(value_mismatches):
            fill = (i % 2 == 0)
            wrapping_table_row([var, val1, val2], [60, 62, 63], fill=fill, fill_rgb=alt_rgb)
    else:
        note("No value mismatches found.")
    pdf.ln(4)

    # --- Malformed Lines ---
    section_title("Malformed Lines")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, "Lines that could not be parsed (no = sign found).", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    sub_title(f"File 1: {file1_name}")
    if malformed1:
        table_header(["Line"], [185])
        for i, entry in enumerate(malformed1):
            table_row([entry], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No malformed lines found.")

    pdf.ln(2)
    sub_title(f"File 2: {file2_name}")
    if malformed2:
        table_header(["Line"], [185])
        for i, entry in enumerate(malformed2):
            table_row([entry], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No malformed lines found.")
    pdf.ln(4)

    # --- Matching Variables ---
    section_title("Matching Variables")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, "Variables present in both files with identical values.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    if matching:
        table_header(["Variable"], [185])
        for i, var in enumerate(matching):
            table_row([var], [185], fill=(i % 2 == 0), fill_rgb=alt_rgb)
    else:
        note("No matching variables found.")

    pdf.output(output_path)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Compare two .env files and generate a local difference report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python env_diff.py --file1 .env.staging --file2 .env.production
  python env_diff.py --file1 .env.staging --file2 .env.production --output-dir ./reports

Windows:
  python env_diff.py --file1 "C:\\projects\\myapp\\.env.staging" ^
                     --file2 "C:\\projects\\myapp\\.env.production" ^
                     --output-dir "C:\\projects\\myapp\\reports"
        """,
    )
    parser.add_argument("--file1", required=True, metavar="PATH",
                        help="Path to the first .env file")
    parser.add_argument("--file2", required=True, metavar="PATH",
                        help="Path to the second .env file")
    parser.add_argument("--output-dir", default=".", metavar="PATH",
                        help="Directory to save reports (default: current directory)")
    args = parser.parse_args()

    file1_name = Path(args.file1).name
    file2_name = Path(args.file2).name

    if not Path(args.file1).exists():
        print(f"Error: File 1 not found: {args.file1}")
        return
    if not Path(args.file2).exists():
        print(f"Error: File 2 not found: {args.file2}")
        return

    if Path(args.file1).resolve() == Path(args.file2).resolve():
        print("Error: --file1 and --file2 point to the same file.")
        print(f"  Resolved path: {Path(args.file1).resolve()}")
        print("  Please provide two different env files.")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Parsing {file1_name}...")
    rows1, dups1, empty1, malformed1 = parse_env_file(args.file1)

    print(f"Parsing {file2_name}...")
    rows2, dups2, empty2, malformed2 = parse_env_file(args.file2)

    print("Comparing files...")
    only_in_1, only_in_2, value_mismatches, matching, dict1, dict2 = compare_files(rows1, rows2)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    base_name = f"env_compared_{timestamp}"
    md_path   = output_dir / f"{base_name}.md"
    pdf_path  = output_dir / f"{base_name}.pdf"

    print(f"Writing {base_name}.md...")
    md_content = generate_markdown(
        file1_name, file2_name,
        rows1, dups1, empty1, malformed1,
        rows2, dups2, empty2, malformed2,
        only_in_1, only_in_2, value_mismatches, matching
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Writing {base_name}.pdf...")
    generate_pdf(
        str(pdf_path), file1_name, file2_name,
        rows1, dups1, empty1, malformed1,
        rows2, dups2, empty2, malformed2,
        only_in_1, only_in_2, value_mismatches, matching
    )

    print(f"\nDone! Reports saved to: {output_dir}")
    print(f"  {base_name}.md")
    print(f"  {base_name}.pdf")


if __name__ == "__main__":
    main()
