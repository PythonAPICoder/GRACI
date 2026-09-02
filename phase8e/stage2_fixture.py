"""Bounded synthetic fixture actions for Phase 8E Stage 2 host validation."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from phase8e.projection import (
    AuthorityClass,
    INITIAL_REPOSITORY_CATALOG,
    MemoryProjectionRequest,
    ProjectionError,
    ProjectionExporter,
    ProjectionVerifier,
    RepositorySource,
    ReviewClassification,
    SourceType,
)


MEMORY_IDS = (
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
)


def _tree(root: Path) -> dict[str, str]:
    import hashlib

    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def export_fixture(repository: Path, commit: str, staging: Path, projection: Path,
                   evidence: Path, generation_id: str) -> dict[str, object]:
    memory = evidence / "synthetic-memory"
    memory.mkdir(parents=True, exist_ok=True)
    fixtures = Path(__file__).parent / "fixtures" / "memory"
    for memory_id in MEMORY_IDS:
        shutil.copy2(fixtures / f"{memory_id}.json", memory / f"{memory_id}.json")
    target = ProjectionExporter(staging, projection).export(
        repository_root=repository,
        source_commit=commit,
        catalog=INITIAL_REPOSITORY_CATALOG,
        generation_id=generation_id,
        memory=MemoryProjectionRequest(memory, MEMORY_IDS,
                                       frozenset({MEMORY_IDS[1]})),
    )
    manifest = ProjectionVerifier(projection).verify_current()
    return {"passed": True, "generation_id": manifest["generation_id"],
            "target": str(target), "entry_count": len(manifest["entries"])}


def failed_refresh(repository: Path, commit: str, staging: Path, projection: Path,
                   evidence: Path, generation_id: str) -> dict[str, object]:
    before = _tree(projection)
    missing = RepositorySource(
        "docs/synthetic-stage2-missing.md", "synthetic/missing.md",
        SourceType.CURRENT_STATE, ReviewClassification.PRODUCT_OWNER_REVIEW,
        AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE,
    )
    failure = None
    try:
        ProjectionExporter(staging, projection).export(
            repository_root=repository, source_commit=commit,
            catalog=INITIAL_REPOSITORY_CATALOG + (missing,), generation_id=generation_id,
        )
    except ProjectionError as exc:
        failure = str(exc)
    after = _tree(projection)
    passed = failure is not None and before == after
    return {"passed": passed, "failure": failure,
            "last_known_good_unchanged": before == after}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("export", "failed-refresh"))
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--projection", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    args = parser.parse_args()
    if args.action == "export":
        result = export_fixture(args.repository, args.commit, args.staging,
                                args.projection, args.evidence, args.generation_id)
    else:
        result = failed_refresh(args.repository, args.commit, args.staging,
                                args.projection, args.evidence, args.generation_id)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
