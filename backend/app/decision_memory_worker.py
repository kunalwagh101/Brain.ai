import argparse

from sqlalchemy import select

from app.database import get_session_factory
from app.decision_memory import reconcile_memory_candidates
from app.models import Organization


def run_once(*, batch_size: int) -> tuple[int, int, int]:
    processed = created = remaining = 0
    factory = get_session_factory()
    with factory() as db:
        organization_ids = list(db.scalars(select(Organization.id)))
        for organization_id in organization_ids:
            org_processed, org_created, org_remaining = reconcile_memory_candidates(
                db,
                organization_id=organization_id,
                limit=batch_size,
            )
            processed += org_processed
            created += org_created
            remaining += org_remaining
    return processed, created, remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Brain decision/blocker memory worker")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        raise SystemExit("Only --once is supported; schedule it with the production job runner")
    if args.batch_size < 1 or args.batch_size > 500:
        raise SystemExit("--batch-size must be between 1 and 500")
    processed, created, remaining = run_once(batch_size=args.batch_size)
    print(
        f"processed_documents={processed} "
        f"created_candidates={created} "
        f"remaining_documents={remaining}"
    )


if __name__ == "__main__":
    main()
