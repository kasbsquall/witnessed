"""Aggregate evidence levels for a set of changed units."""

from __future__ import annotations

from typing import Literal

Level = Literal["used", "tested", "agent_witnessed", "unwitnessed"]

_STRENGTH: dict[Level, int] = {
    "used": 3,
    "tested": 2,
    "agent_witnessed": 1,
    "unwitnessed": 0,
}

_LABEL: dict[Level, str] = {
    "used": "used in real runs",
    "tested": "only by tests",
    "agent_witnessed": "only by an agent's witness",
    "unwitnessed": "never seen running",
}


def level_label(level: Level) -> str:
    """Return the plain-English label for *level*."""
    return _LABEL[level]


def pr_verdict(levels: list[Level]) -> Level:
    """Return the weakest level among *levels*.

    If *levels* is empty, returns 'unwitnessed'.
    """
    if not levels:
        return "unwitnessed"
    return min(levels, key=lambda lv: _STRENGTH[lv])
