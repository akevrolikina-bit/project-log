"""Tests for the Jira worklog Excel parser using the real sample file."""

from datetime import datetime
from pathlib import Path

import pytest

from app.schemas.worklog import WorklogEntry
from app.services.excel_parser import parse_worklog_file

SAMPLE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "input" / "Time Sheet Report 2026.05.xls"


@pytest.fixture(scope="module")
def entries() -> list[WorklogEntry]:
    """Parse the sample file once and reuse across tests in this module."""
    assert SAMPLE_FILE.exists(), f"Sample file not found: {SAMPLE_FILE}"
    return parse_worklog_file(SAMPLE_FILE)


def test_parses_expected_row_count(entries: list[WorklogEntry]):
    assert len(entries) > 1000, f"Expected >1000 rows, got {len(entries)}"


def test_returns_worklog_entry_objects(entries: list[WorklogEntry]):
    assert all(isinstance(e, WorklogEntry) for e in entries)


def test_first_entry_fields(entries: list[WorklogEntry]):
    first = entries[0]
    assert first.project, "Project must not be empty"
    assert first.key, "Key must not be empty"
    assert first.username, "Username must not be empty"
    assert first.hours > 0, "Hours must be positive"


def test_dates_are_parsed(entries: list[WorklogEntry]):
    for entry in entries[:50]:
        assert isinstance(entry.started, datetime)
        assert entry.started.year == 2026


def test_hours_are_numeric(entries: list[WorklogEntry]):
    for entry in entries:
        assert isinstance(entry.hours, float)
        assert entry.hours > 0


def test_no_html_tags_in_text_fields(entries: list[WorklogEntry]):
    import re
    html_tag_re = re.compile(r"<[a-zA-Z/][^>]*>")
    for entry in entries[:100]:
        for field in (entry.project, entry.task_type, entry.key, entry.title, entry.comment):
            assert not html_tag_re.search(field), f"HTML tag found in field value: {field!r}"


def test_all_fields_present(entries: list[WorklogEntry]):
    first = entries[0]
    for field_name in ("project", "task_type", "key", "title", "started", "username", "hours", "comment"):
        assert getattr(first, field_name) is not None, f"Field {field_name} is None"


def test_parse_from_bytes():
    """Parser should also accept raw bytes (as used by API upload)."""
    raw = SAMPLE_FILE.read_bytes()
    entries = parse_worklog_file(raw)
    assert len(entries) > 1000
