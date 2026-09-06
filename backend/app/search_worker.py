import argparse

from sqlalchemy import select

from app.database import get_session_factory
from app.embeddings import EmbeddingError, build_embedding_client
from app.models import Organization
from app.search import process_embedding_batch, reconcile_search_documents


def run_once(*, batch_size: int) -> tuple[int, int, int]:
    try:
        client, model = build_embedding_client()
    except EmbeddingError as exc:
        raise SystemExit(f"Embedding configuration unavailable: {exc}") from exc
    if client is None or model is None:
        raise SystemExit("Embedding service is not configured")

    reconciled = embedded = failed = 0
    factory = get_session_factory()
    with factory() as db:
        organization_ids = list(db.scalars(select(Organization.id)))
        for organization_id in organization_ids:
            processed, _ = reconcile_search_documents(
                db,
                organization_id=organization_id,
                limit=batch_size,
            )
            reconciled += processed
        embedded, failed = process_embedding_batch(
            db,
            embedding_client=client,
            model=model,
            limit=batch_size,
        )
    return reconciled, embedded, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Brain search projection/embedding worker")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        raise SystemExit("Only --once is supported; schedule it with the production job runner")
    if args.batch_size < 1 or args.batch_size > 500:
        raise SystemExit("--batch-size must be between 1 and 500")
    reconciled, embedded, failed = run_once(batch_size=args.batch_size)
    print(f"reconciled={reconciled} embedded={embedded} failed={failed}")


if __name__ == "__main__":
    main()
