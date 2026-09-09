import argparse

from app.agent_maintenance import maintain_agent_runtime
from app.database import get_session_factory


def run_once(*, batch_size: int) -> int:
    factory = get_session_factory()
    with factory() as db:
        result = maintain_agent_runtime(db, limit=batch_size)
    print(
        "agent-maintenance "
        f"approvals_expired={result.approvals_expired} "
        f"planning_recovered={result.planning_recovered} "
        f"executions_recovered={result.executions_recovered} "
        f"executions_failed_closed={result.executions_failed_closed}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain governed agent runtime state")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not args.once:
        parser.error("Only bounded --once execution is supported")
    if args.batch_size < 1 or args.batch_size > 500:
        parser.error("--batch-size must be between 1 and 500")
    return run_once(batch_size=args.batch_size)


if __name__ == "__main__":
    raise SystemExit(main())
