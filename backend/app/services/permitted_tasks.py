"""Load the permitted-task list from the Issues CHANGE Excel export.

The "LOG" sheet has two kinds of rules:

1. **Key-based rules** (rows with a Jira key in column D):
       A=Project, B=Type, C=Group, D=Key, E=Title, F="да"/"нет", G=Exclusions

2. **Project+Type rules** (rows with Project+Type but no Key):
       A=Project, B=Type, F="да"/"нет", G=Exclusions
       These act as catch-all rules for any key under that project/type combo.

Exclusion formats in column G:
    - "Носов Михаил"                  — this person is excluded
    - "все, кроме Носова Михаила"     — only the named person is allowed
    - empty                           — no exclusions
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "input" / "Issues CHANGE (1).xlsx"
)


COMMENT_RULE_STRICT = "strict"
COMMENT_RULE_LENIENT = "lenient"


@dataclass
class KeyRule:
    """Rule for a specific Jira key."""

    project: str
    task_type: str
    key: str
    title: str
    permitted: bool
    excluded_users: list[str] = field(default_factory=list)
    only_users: list[str] = field(default_factory=list)
    comment_rule: str = ""


@dataclass
class ProjectTypeRule:
    """Catch-all rule for a Project + Type combination."""

    project: str
    task_type: str
    permitted: bool
    excluded_users: list[str] = field(default_factory=list)
    only_users: list[str] = field(default_factory=list)
    comment_rule: str = ""


@dataclass
class CheckVerdict:
    """Result of checking a single worklog entry against the registry."""

    permitted: bool
    reason: str
    rule_type: str  # "key", "project_type", or "unknown"


def _parse_exclusions(raw: str) -> tuple[list[str], list[str]]:
    """Parse the exclusion column.

    Returns (excluded_users, only_users).
    - excluded_users: people who are NOT allowed even though the task is "да".
    - only_users: if non-empty, ONLY these people are allowed.
    """
    raw = raw.strip()
    if not raw:
        return [], []

    krome_match = re.match(
        r"все[,.]?\s*кроме\s+(.+)", raw, re.IGNORECASE
    )
    if krome_match:
        names_part = krome_match.group(1).strip()
        only = [n.strip() for n in re.split(r"[,;]", names_part) if n.strip()]
        return [], only

    excluded = [n.strip() for n in re.split(r"[,;]", raw) if n.strip()]
    return excluded, []


def _name_key(name: str) -> str:
    """Normalize a Russian name for comparison.

    Strips case-endings by taking the first 3 chars of surname + first 3 chars
    of first name, so "Носов Михаил" and "Носова Михаила" both produce "нос мих".
    """
    parts = name.strip().split()
    return " ".join(p[:3].lower() for p in parts if p)


def _names_match(a: str, b: str) -> bool:
    return _name_key(a) == _name_key(b)


class PermittedTasksRegistry:
    """Two-level lookup: by Jira key, then by project+type."""

    def __init__(self) -> None:
        self._key_rules: dict[str, KeyRule] = {}
        self._pt_rules: dict[tuple[str, str], ProjectTypeRule] = {}
        self.time_limited_keys: set[str] = set()
        self.general_rules: list[str] = []

    def add_key_rule(self, rule: KeyRule) -> None:
        self._key_rules[rule.key] = rule

    def add_project_type_rule(self, rule: ProjectTypeRule) -> None:
        self._pt_rules[(rule.project, rule.task_type)] = rule

    def check(self, key: str, project: str, task_type: str, username: str) -> CheckVerdict:
        """Check whether this worklog entry is permitted for the given user.

        Lookup order:
        1. Specific key rule
        2. Project + Type catch-all rule
        3. Unknown (no rule found)
        """
        kr = self._key_rules.get(key)
        if kr is not None:
            return self._apply_rule(
                permitted=kr.permitted,
                excluded_users=kr.excluded_users,
                only_users=kr.only_users,
                username=username,
                rule_type="key",
                label=kr.key,
            )

        ptr = self._pt_rules.get((project, task_type))
        if ptr is not None:
            return self._apply_rule(
                permitted=ptr.permitted,
                excluded_users=ptr.excluded_users,
                only_users=ptr.only_users,
                username=username,
                rule_type="project_type",
                label=f"{project}/{task_type}",
            )

        return CheckVerdict(
            permitted=False,
            reason=f"Задача {key} ({project}/{task_type}) отсутствует в списке разрешённых",
            rule_type="unknown",
        )

    @staticmethod
    def _apply_rule(
        *,
        permitted: bool,
        excluded_users: list[str],
        only_users: list[str],
        username: str,
        rule_type: str,
        label: str,
    ) -> CheckVerdict:
        if not permitted:
            return CheckVerdict(
                permitted=False,
                reason=f"Задача {label} запрещена для списания",
                rule_type=rule_type,
            )

        if only_users:
            if not any(_names_match(username, name) for name in only_users):
                return CheckVerdict(
                    permitted=False,
                    reason=f"Задача {label} разрешена только для: {', '.join(only_users)}",
                    rule_type=rule_type,
                )

        if excluded_users:
            for excl_name in excluded_users:
                if _names_match(username, excl_name):
                    return CheckVerdict(
                        permitted=False,
                        reason=f"Сотруднику {username} запрещено списывать на {label}",
                        rule_type=rule_type,
                    )

        return CheckVerdict(permitted=True, reason="OK", rule_type=rule_type)

    def get_comment_rule(self, key: str, project: str, task_type: str) -> str:
        """Return the comment rule for a task: 'strict', 'lenient', or ''."""
        kr = self._key_rules.get(key)
        if kr is not None:
            return kr.comment_rule

        ptr = self._pt_rules.get((project, task_type))
        if ptr is not None:
            return ptr.comment_rule

        return ""

    @property
    def key_rules(self) -> dict[str, KeyRule]:
        return dict(self._key_rules)

    @property
    def project_type_rules(self) -> dict[tuple[str, str], ProjectTypeRule]:
        return dict(self._pt_rules)


_TIME_LIMITED_KEYS = {"BUH-72900", "BUH-115258"}


def _parse_comment_rule(raw: str) -> str:
    """Classify the comment rule text into a machine-usable constant."""
    raw = raw.strip().lower()
    if not raw:
        return ""
    if "может не быть" in raw or "может быть комментарий" in raw:
        return COMMENT_RULE_LENIENT
    if "не может быть пустым" in raw:
        return COMMENT_RULE_STRICT
    return COMMENT_RULE_STRICT


def load_permitted_tasks(path: str | Path | None = None) -> PermittedTasksRegistry:
    """Parse the Excel file and return a registry.

    Parameters
    ----------
    path : path to the .xlsx file.  Defaults to
           ``data/input/Issues CHANGE (1).xlsx`` relative to project root.
           Can also be set via ``PERMITTED_TASKS_PATH`` env var.
    """
    if path is None:
        path = os.environ.get("PERMITTED_TASKS_PATH", str(_DEFAULT_PATH))
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Permitted-tasks file not found: {path}")

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)

    sheet_name = "LOG"
    if sheet_name not in wb.sheetnames:
        sheet_name = wb.sheetnames[0]

    ws = wb[sheet_name]
    registry = PermittedTasksRegistry()
    registry.time_limited_keys = set(_TIME_LIMITED_KEYS)

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 2:
            continue

        proj = str(row[0]).strip() if row[0] else ""
        typ = str(row[1]).strip() if row[1] else ""
        group = str(row[2]).strip() if row[2] else ""
        key = str(row[3]).strip() if row[3] else ""
        title = str(row[4]).strip() if row[4] else ""
        status_raw = str(row[5]).strip().lower() if row[5] else ""
        excl_raw = str(row[6]).strip() if len(row) > 6 and row[6] else ""
        comment_rule_raw = str(row[7]).strip() if len(row) > 7 and row[7] else ""

        # General rules at the bottom (no status "да"/"нет")
        if status_raw not in ("да", "нет"):
            if proj and not key and not typ:
                text = proj.strip()
                if text and not text.startswith("Project"):
                    registry.general_rules.append(text)
            continue

        permitted = status_raw == "да"
        excluded_users, only_users = _parse_exclusions(excl_raw)
        comment_rule = _parse_comment_rule(comment_rule_raw)

        if key and "-" in key:
            registry.add_key_rule(
                KeyRule(
                    project=proj,
                    task_type=typ,
                    key=key,
                    title=title,
                    permitted=permitted,
                    excluded_users=excluded_users,
                    only_users=only_users,
                    comment_rule=comment_rule,
                )
            )
        elif proj and typ:
            registry.add_project_type_rule(
                ProjectTypeRule(
                    project=proj,
                    task_type=typ,
                    permitted=permitted,
                    excluded_users=excluded_users,
                    only_users=only_users,
                    comment_rule=comment_rule,
                )
            )

    wb.close()
    return registry
