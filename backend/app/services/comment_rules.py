"""Rule-based comment quality checks (no AI required).

Each check function returns a list of CommentIssue dataclass instances
describing problems found in the comment text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_DEFAULT_JIRA_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Working on issue\s+\S+\.?$", re.IGNORECASE),
    re.compile(r"^Работа над задачей\s+\S+\.?$", re.IGNORECASE),
    re.compile(r"^Work on\s+\S+\.?$", re.IGNORECASE),
]

_MIN_MEANINGFUL_LENGTH = 10

_SHORT_COMMENT_ALLOWED: dict[str, list[re.Pattern[str]]] = {
    "BUH-115258": [re.compile(r"почт", re.IGNORECASE)],
    "BUH-115259": [re.compile(r"статус", re.IGNORECASE)],
    "GENERAL-121": [re.compile(r"отгул", re.IGNORECASE)],
}


@dataclass
class CommentIssue:
    severity: str  # "error" | "warning"
    reason: str


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip()


def _short_comment_allowed(key: str, text: str) -> bool:
    """Return True when a short comment is acceptable for the given task key."""
    patterns = _SHORT_COMMENT_ALLOWED.get(key)
    if not patterns:
        return False
    return any(p.search(text) for p in patterns)


def check_comment_quality(
    comment: str,
    key: str,
    title: str,
    comment_rule: str = "",
) -> list[CommentIssue]:
    """Run rule-based checks on a single worklog comment.

    Parameters
    ----------
    comment_rule : "strict", "lenient", or "".
        - "lenient" means empty comments and default Jira comments are acceptable.
        - "strict" or "" applies the full check suite.

    Returns an empty list when the comment is acceptable.
    """
    if comment_rule == "lenient":
        return []

    issues: list[CommentIssue] = []
    clean = _normalize(comment)

    if not clean:
        issues.append(CommentIssue(
            severity="error",
            reason=f"Пустой комментарий к задаче {key}",
        ))
        return issues

    for pat in _DEFAULT_JIRA_PATTERNS:
        if pat.match(clean):
            issues.append(CommentIssue(
                severity="error",
                reason=(
                    f"Стандартный комментарий Jira к задаче {key}: "
                    f"«{clean}»"
                ),
            ))
            return issues

    if len(clean) < _MIN_MEANINGFUL_LENGTH and not _short_comment_allowed(key, clean):
        issues.append(CommentIssue(
            severity="error",
            reason=(
                f"Слишком короткий комментарий ({len(clean)} симв.) "
                f"к задаче {key}: «{clean}»"
            ),
        ))

    clean_title = _normalize(title)
    if clean_title and clean.lower() == clean_title.lower():
        issues.append(CommentIssue(
            severity="error",
            reason=(
                f"Комментарий совпадает с названием задачи {key}: "
                f"«{clean}»"
            ),
        ))

    return issues
