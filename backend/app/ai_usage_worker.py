import argparse

from sqlalchemy import select

from app.ai_usage_reconciliation import reconcile_usage_costs
from app.database import get_session_factory
from app.models import Organization


def run_once(*, batch_size: int) -> tuple[int, int, int]:
    processed = resolved = remaining = 0
    factory = get_session_factory()
    with factory() as db:
        organization_ids = list(db.scalars(select(Organization.id)))
        for organization_id in organization_ids:
            org_processed, org_resolved, org_remaining = reconcile_usage_costs(
                db,
                organization_id=organization_id,
                limit=batch_size,
            )
            processed += org_processed
            resolved += org_resolved
            remaining += org_remaining
    return processed, resolved, remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Brain AI usage-cost reconciliation worker")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        raise SystemExit("Only --once is supported; schedule it with the production job runner")
    if args.batch_size < 1 or args.batch_size > 500:
        raise SystemExit("--batch-size must be between 1 and 500")
    processed, resolved, remaining = run_once(batch_size=args.batch_size)
    print(f"processed={processed} resolved={resolved} remaining={remaining}")


if __name__ == "__main__":
    main()
