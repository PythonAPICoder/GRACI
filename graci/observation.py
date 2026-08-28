"""Small optional runtime-observation boundary.

Observers receive trusted lifecycle facts only.  They are never authoritative and
their failures are deliberately isolated from execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


_LOG = logging.getLogger(__name__)


class ObservationKind(str, Enum):
    TASK_STARTED = "task_started"
    PLANNING_STARTED = "planning_started"
    MEMORY_STARTED = "memory_started"
    MEMORY_COMPLETED = "memory_completed"
    MODEL_STARTED = "model_started"
    MODEL_COMPLETED = "model_completed"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TESTS_STARTED = "tests_started"
    TESTS_COMPLETED = "tests_completed"
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    ADJUDICATION_STARTED = "adjudication_started"
    ADJUDICATION_COMPLETED = "adjudication_completed"
    ROUTE_COMPLETED = "route_completed"
    TASK_COMPLETED = "task_completed"
    TASK_WARNING = "task_warning"
    TASK_FAILED = "task_failed"


@dataclass(frozen=True)
class RuntimeObservation:
    kind: ObservationKind
    timestamp: datetime
    run_id: str
    facts: tuple[tuple[str, Any], ...] = ()


class RuntimeObserver(Protocol):
    def observe(self, observation: RuntimeObservation) -> None: ...


def observe(observer: RuntimeObserver | None, kind: ObservationKind, run_id: str,
            **facts: Any) -> None:
    """Publish synchronously in-process and fail open on every observer error."""
    if observer is None:
        return
    item = RuntimeObservation(kind, datetime.now(timezone.utc), run_id,
                              tuple(sorted(facts.items())))
    try:
        observer.observe(item)
    except Exception as exc:  # observation cannot change the authoritative result
        _LOG.warning("runtime observer failed (%s): %s", type(exc).__name__, exc)
