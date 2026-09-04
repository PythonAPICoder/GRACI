"""Maintainer-only refresh for one exact synthetic personalized-memory generation.

This helper is explicitly invoked with exact repository, vault, staging, and
projection identities. It does not select current state, start timers, launch an
application, refresh automatically, or grant authority.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from graci.personalized_memory import SyntheticPersonalizedMemoryRepository

from .personalized_projection import build_personalized_projection_request
from .projection import (MemoryProjectionRequest, ProjectionError, ProjectionExporter,
                         ProjectionVerifier, RepositorySource)


def refresh_synthetic_vault(
        *,
        repository: SyntheticPersonalizedMemoryRepository,
        memory_generation_id: str,
        vault_generation_id: str,
        repository_root: Path,
        source_commit: str,
        catalog: Sequence[RepositorySource],
        staging_root: Path,
        projection_root: Path,
        memory_request: MemoryProjectionRequest | None = None,
        clock: Callable[[], datetime] | None = None) -> dict[str, object]:
    """Export and verify one exact synthetic generation into an immutable vault."""
    request = memory_request or build_personalized_projection_request(
        repository, generation_id=memory_generation_id)
    expected_memory_root = repository.snapshot(memory_generation_id).memory_root
    if request.root.resolve(strict=False) != expected_memory_root.resolve(strict=False):
        raise ProjectionError("memory request and repository disagree on the synthetic root")
    exporter = ProjectionExporter(staging_root, projection_root, clock=clock)
    generation = exporter.export(
        repository_root=repository_root,
        source_commit=source_commit,
        catalog=catalog,
        generation_id=vault_generation_id,
        memory=request,
    )
    manifest = ProjectionVerifier(projection_root).verify_current()
    if manifest["generation_id"] != vault_generation_id:
        raise ProjectionError("vault generation identity mismatch")
    return {
        "memory_generation_id": memory_generation_id,
        "vault_generation_id": vault_generation_id,
        "generation": generation,
        "manifest": manifest,
    }
