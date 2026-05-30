"""Parser for Jira time-sheet exports (.xls files that are actually HTML tables)."""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Union

import pandas as pd

from app.schemas.worklog import WorklogEntry

_EXPECTED_COLUMNS = [
    "Project",
    "Type",
    "Key",
    "Title",
    "Started",
    "Username",
    "Time Spent (Hours)",
    "Comment",
]

_DATE_FORMAT = "%d.%m.%Y %H:%M"

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: object) -> str:
    """Remove residual HTML tags and collapse whitespace."""
    text = str(value) if not isinstance(value, str) else value
    text = _HTML_TAG_RE.sub("", text)
    return " ".join(text.split())


def _read_html_table(source: Union[str, Path, bytes, BinaryIO]) -> pd.DataFrame:
    """Read the data table from *source* using the lxml backend.

    The Jira export wraps the real data table inside an outer layout table,
    so we iterate over all parsed tables and pick the one whose columns
    match the expected header row.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        raw = path.read_bytes()
    elif isinstance(source, bytes):
        raw = source
    else:
        raw = source.read()

    html_text = raw.decode("utf-8", errors="replace")

    tables = pd.read_html(io.StringIO(html_text), flavor="lxml")
    if not tables:
        raise ValueError("No HTML tables found in the provided file.")

    expected_set = set(_EXPECTED_COLUMNS)
    for table in tables:
        if set(table.columns) == expected_set:
            return table

    # Jira uses <td> instead of <th> for header cells, so pandas may not
    # detect the header row automatically.  Fall back to the table with the
    # right number of columns and promote the first row to headers.
    n_cols = len(_EXPECTED_COLUMNS)
    for table in tables:
        if len(table.columns) == n_cols:
            first_row = [str(v).strip() for v in table.iloc[0]]
            if set(first_row) == expected_set:
                table.columns = first_row
                table = table.iloc[1:].reset_index(drop=True)
                return table

    raise ValueError(
        f"None of the {len(tables)} HTML tables has the expected columns. "
        f"Found column sets: {[list(t.columns) for t in tables]}"
    )


def parse_worklog_file(
    source: Union[str, Path, bytes, BinaryIO],
) -> list[WorklogEntry]:
    """Parse a Jira HTML-based .xls export and return structured worklog entries.

    *source* can be a file path (str / Path), raw bytes, or a file-like object
    (e.g. ``UploadFile.file`` from FastAPI).
    """
    df = _read_html_table(source)

    if list(df.columns) != _EXPECTED_COLUMNS:
        raise ValueError(
            f"Unexpected columns: {list(df.columns)}. "
            f"Expected: {_EXPECTED_COLUMNS}"
        )

    # Drop summary / empty rows (e.g. the "Total" footer row).
    df = df.dropna(subset=["Started"]).reset_index(drop=True)

    entries: list[WorklogEntry] = []
    for _, row in df.iterrows():
        started = datetime.strptime(str(row["Started"]).strip(), _DATE_FORMAT)
        hours = float(row["Time Spent (Hours)"])

        comment_raw = row["Comment"]
        comment = "" if pd.isna(comment_raw) else _strip_html(comment_raw)

        entries.append(
            WorklogEntry(
                project=_strip_html(row["Project"]),
                task_type=_strip_html(row["Type"]),
                key=_strip_html(row["Key"]),
                title=_strip_html(row["Title"]),
                started=started,
                username=_strip_html(row["Username"]),
                hours=hours,
                comment=comment,
            )
        )

    return entries
