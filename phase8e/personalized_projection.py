"""Explicit adapter from synthetic personalized memory to Phase 8E projection."""

from __future__ import annotations

from collections import defaultdict

from graci.memory import MemoryStatus, MemoryStore, MemoryValidationError, _parse_timestamp
from graci.personalized_memory import SyntheticPersonalizedMemoryRepository

from .projection import (ConflictState, MAX_MEMORY_RECORDS,
                         MemoryProjectionRequest, ProjectionError)


def build_personalized_projection_request(
        repository: SyntheticPersonalizedMemoryRepository, *,
        generation_id: str) -> MemoryProjectionRequest:
    """Build an exact, manual projection request for one verified generation.

    The adapter does not refresh or promote a vault. It only names the immutable
    synthetic record root and exact approved record IDs for a later explicit export.
    """
    snapshot = repository.snapshot(generation_id)
    listing = MemoryStore(snapshot.memory_root).enumerate(limit=MAX_MEMORY_RECORDS)
    if listing.has_more or listing.corruptions:
        raise ProjectionError("personalized-memory generation is incomplete or corrupt")
    records = tuple(listing.records)
    if not records:
        raise ProjectionError("personalized-memory generation contains no approved records")
    ids = tuple(record["memory_id"] for record in records)
    if ids != snapshot.memory_ids:
        raise ProjectionError("personalized-memory manifest and records disagree")

    try:
        now = repository.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise MemoryValidationError("clock must return a timezone-aware timestamp")
    except (MemoryValidationError, TypeError, ValueError) as exc:
        raise ProjectionError("personalized-memory clock is invalid") from exc

    groups: dict[tuple[str, str | None, str, str], list[str]] = defaultdict(list)
    for record in records:
        if record["status"] != MemoryStatus.ACTIVE.value:
            continue
        expires_at = record["expires_at"]
        if expires_at is not None and _parse_timestamp(expires_at, "expires_at") <= now:
            continue
        scope = record["scope"]
        groups[(scope["kind"], scope["id"], record["relevance_key"],
                record["memory_type"])].append(record["memory_id"])
    conflict_ids = {
        memory_id
        for grouped_ids in groups.values() if len(grouped_ids) > 1
        for memory_id in grouped_ids
    }
    conflicts = {memory_id: ConflictState.REPORTED for memory_id in conflict_ids}
    return MemoryProjectionRequest(
        root=snapshot.memory_root,
        memory_ids=ids,
        approved_content_ids=frozenset(ids),
        conflicts=conflicts,
    )
