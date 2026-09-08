import argparse
import logging

from sqlalchemy import select

from app.data_governance import (
    DataGovernanceError,
    execute_deletion_request,
    pending_deletion_requests,
    run_retention_once,
)
from app.database import get_session_factory
from app.models import Organization
from app.observability import log_event

logger = logging.getLogger("brain.data_governance")


def run_once(*, batch_size: int = 100) -> tuple[int, int, int]:
    if batch_size < 1 or batch_size > 500:
        raise ValueError("batch_size must be 1-500")
    factory = get_session_factory()
    retention_runs = 0
    deletions_completed = 0
    deletions_failed = 0
    with factory() as db:
        organization_ids = list(db.scalars(select(Organization.id).order_by(Organization.id)))

    for organization_id in organization_ids:
        with factory() as db:
            try:
                run = run_retention_once(
                    db,
                    organization_id=organization_id,
                    limit=batch_size,
                )
                retention_runs += int(run is not None)
            except DataGovernanceError:
                deletions_failed += 1
                log_event(
                    logger,
                    logging.ERROR,
                    "retention.run.failed",
                    organization_id=organization_id,
                    error_code="retention_failed",
                    worker="data_governance",
                )

        with factory() as db:
            pending = pending_deletion_requests(
                db,
                organization_id=organization_id,
                limit=batch_size,
            )
            request_ids = [item.id for item in pending]
            db.rollback()

        for deletion_request_id in request_ids:
            with factory() as db:
                try:
                    execute_deletion_request(
                        db,
                        organization_id=organization_id,
                        deletion_request_id=deletion_request_id,
                    )
                    deletions_completed += 1
                except DataGovernanceError:
                    deletions_failed += 1
                    log_event(
                        logger,
                        logging.ERROR,
                        "deletion.request.failed",
                        organization_id=organization_id,
                        error_code="deletion_failed",
                        worker="data_governance",
                    )

    log_event(
        logger,
        logging.INFO,
        "data_governance.worker.completed",
        worker="data_governance",
        processed=retention_runs + deletions_completed,
        remaining=deletions_failed,
    )
    return retention_runs, deletions_completed, deletions_failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one bounded data-governance pass")
    parser.add_argument("--once", action="store_true", help="Run one pass and exit")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        parser.error("Only --once is supported; schedule this command in the job runner")
    run_once(batch_size=args.batch_size)


if __name__ == "__main__":
    main()
