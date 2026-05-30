"""Load employee-to-country mapping from config/employee_countries.json."""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "employee_countries.json"

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    with open(_CONFIG_PATH, encoding="utf-8") as f:
        _cache = json.load(f)
    return _cache


def get_country(username: str) -> str:
    """Return the country code (RU/KZ/BY) for the given employee.

    Falls back to the 'default' value from config if the employee is unknown.
    """
    data = _load()
    return data["employees"].get(username, data.get("default", "RU"))
