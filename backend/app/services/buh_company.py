"""Parse GBS JIRA CSV exports to extract BUH Company per issue key.

The CSV files are UTF-8 (sometimes with BOM) and have varying column counts
across different exports.  Columns are located by header name, not index.
"""

from __future__ import annotations

import csv
import io

MENA_BUH_COMPANIES: set[str] = {
    "DBFZ - Databorn FZ LLC",
    "DBSA - Databorn Company Limited LLC",
    "DBAD - Databorn FZ LLC Abu Dhabi",
}

ALPHYN_BUH_COMPANIES: set[str] = {
    "ALFZ - Alphyn AI FZ LLC",
}

_KEY_HEADER = "Issue key"
_BUH_HEADER = "Custom field (BUH Company)"


def parse_buh_csv(file_content: bytes) -> dict[str, str]:
    """Parse a single CSV and return a mapping of issue key → BUH Company.

    Skips rows where the key or company value is empty.
    """
    text = file_content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))

    header = next(reader, None)
    if header is None:
        return {}

    key_idx: int | None = None
    buh_idx: int | None = None
    for idx, col_name in enumerate(header):
        stripped = col_name.strip()
        if stripped == _KEY_HEADER:
            key_idx = idx
        elif stripped == _BUH_HEADER:
            buh_idx = idx

    if key_idx is None or buh_idx is None:
        return {}

    result: dict[str, str] = {}
    for row in reader:
        if key_idx >= len(row) or buh_idx >= len(row):
            continue
        issue_key = row[key_idx].strip()
        buh_company = row[buh_idx].strip()
        if issue_key and buh_company:
            result[issue_key] = buh_company

    return result


def merge_buh_companies(files: list[bytes]) -> dict[str, str]:
    """Parse multiple CSV files and merge results (last file wins on conflict)."""
    merged: dict[str, str] = {}
    for content in files:
        merged.update(parse_buh_csv(content))
    return merged


def resolve_invest_project(buh_company: str) -> str | None:
    """Return the invest project name for a BUH Company value, or None."""
    if buh_company in MENA_BUH_COMPANIES:
        return "MENA"
    if buh_company in ALPHYN_BUH_COMPANIES:
        return "Alphyn"
    return None
