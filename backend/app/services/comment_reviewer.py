"""AI-powered comment relevance review using OpenAI GPT-4o-mini.

Evaluates whether worklog comments are meaningful and relevant
to the task they are logged against.  Returns a traffic-light
verdict: green (ok) / yellow (questionable) / red (irrelevant).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_BATCH_SIZE = 15
_MAX_ENTRIES = 150

_SYSTEM_PROMPT = """\
You are an auditor reviewing employee time-log comments in a Jira-based system.

For each worklog entry you receive a task context (project, key, title, type)
and the employee's comment.  Evaluate whether the comment is meaningful and
relevant to the task.

Return a JSON array with one object per entry, in the same order:
[
  {
    "index": 0,
    "verdict": "green",
    "explanation": "..."
  }
]

Verdict values:
- "green"  — comment is relevant and meaningful for the given task
- "yellow" — comment is vague, generic, or only loosely related to the task
- "red"    — comment is clearly irrelevant to the task, or nonsensical

Keep explanations concise (one sentence, in Russian).
Respond ONLY with the JSON array, no markdown fences.
"""


@dataclass
class CommentVerdict:
    index: int
    verdict: str  # "green" | "yellow" | "red"
    explanation: str


@dataclass
class WorklogForReview:
    """Minimal worklog data needed for AI review."""

    index: int
    project: str
    task_type: str
    key: str
    title: str
    comment: str
    username: str
    hours: float


def _build_user_prompt(entries: list[WorklogForReview]) -> str:
    items = []
    for e in entries:
        items.append(
            f"[{e.index}] Задача: {e.project} / {e.key} / «{e.title}» (тип: {e.task_type})\n"
            f"    Комментарий: «{e.comment}»"
        )
    return "\n\n".join(items)


def _parse_response(text: str, batch_size: int) -> list[CommentVerdict]:
    """Parse the JSON array returned by the model."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse AI response as JSON: %s", text[:200])
        return []

    verdicts: list[CommentVerdict] = []
    for item in data:
        verdict_value = str(item.get("verdict", "yellow")).lower()
        if verdict_value not in ("green", "yellow", "red"):
            verdict_value = "yellow"
        verdicts.append(
            CommentVerdict(
                index=int(item.get("index", -1)),
                verdict=verdict_value,
                explanation=str(item.get("explanation", "")),
            )
        )
    return verdicts


def is_available() -> bool:
    """Check whether the OpenAI API key is configured."""
    return bool(settings.openai_api_key)


def review_comments(
    entries: list[WorklogForReview],
) -> list[CommentVerdict]:
    """Send worklog comments to GPT-4o-mini in batches and return verdicts.

    Entries with empty comments should be pre-filtered by the caller.
    Returns an empty list when the API key is not configured.
    """
    if not is_available():
        logger.info("OpenAI API key not configured — skipping AI comment review")
        return []

    if len(entries) > _MAX_ENTRIES:
        logger.info(
            "Limiting AI review to %d entries (out of %d)",
            _MAX_ENTRIES,
            len(entries),
        )
        entries = entries[:_MAX_ENTRIES]

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=30.0,
    )
    all_verdicts: list[CommentVerdict] = []
    total_batches = (len(entries) + _BATCH_SIZE - 1) // _BATCH_SIZE

    for batch_start in range(0, len(entries), _BATCH_SIZE):
        batch = entries[batch_start : batch_start + _BATCH_SIZE]
        batch_num = batch_start // _BATCH_SIZE + 1
        logger.info("AI review batch %d/%d (%d entries)", batch_num, total_batches, len(batch))
        user_prompt = _build_user_prompt(batch)

        try:
            completion = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            response_text = completion.choices[0].message.content or ""
            verdicts = _parse_response(response_text, len(batch))
            all_verdicts.extend(verdicts)
        except Exception:
            logger.exception(
                "OpenAI API error for batch %d/%d", batch_num, total_batches
            )

    return all_verdicts
