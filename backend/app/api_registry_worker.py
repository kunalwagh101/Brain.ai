import argparse
import logging

from sqlalchemy import select

from app.api_registry import expire_due_api_grants
from app.api_registry_models import APICredentialGrant, APIGrantStatus
from app.database import get_session_factory
from app.secrets import SecretStoreError, get_secret_store

logger = logging.getLogger("brain.api_registry")


def run_once(*, batch_size: int) -> tuple[int, int, int]:
    factory = get_session_factory()
    secret_store = get_secret_store()
    with factory() as db:
        expired = expire_due_api_grants(db, limit=batch_size)
        cleanup_query = (
            select(APICredentialGrant)
            .where(
                APICredentialGrant.status == APIGrantStatus.EXPIRED,
                APICredentialGrant.secret_ref.is_not(None),
            )
            .order_by(APICredentialGrant.expired_at, APICredentialGrant.id)
            .limit(batch_size)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            cleanup_query = cleanup_query.with_for_update(skip_locked=True)
        grants = list(db.scalars(cleanup_query))
        cleaned = failed = 0
        for grant in grants:
            reference = grant.secret_ref
            if reference is None:
                continue
            try:
                secret_store.schedule_delete(reference)
            except SecretStoreError:
                failed += 1
                logger.exception(
                    "Failed to schedule expired API credential secret deletion",
                    extra={"grant_id": str(grant.id)},
                )
                continue
            grant.secret_ref = None
            db.commit()
            cleaned += 1
    return expired, cleaned, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Brain API credential expiry worker")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        raise SystemExit("Only --once is supported; schedule it with the production job runner")
    if args.batch_size < 1 or args.batch_size > 500:
        raise SystemExit("--batch-size must be between 1 and 500")
    expired, cleaned, failed = run_once(batch_size=args.batch_size)
    print(f"expired={expired} secrets_cleaned={cleaned} cleanup_failed={failed}")


if __name__ == "__main__":
    main()
