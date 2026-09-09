import uuid
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session


class AgentRunBusyError(RuntimeError):
    pass


def _lock_key(run_id: uuid.UUID) -> int:
    return int.from_bytes(run_id.bytes[:8], byteorder="big", signed=True)


@contextmanager
def agent_run_lock(db: Session, run_id: uuid.UUID) -> Iterator[None]:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        yield
        return

    key = _lock_key(run_id)
    with bind.connect() as connection:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": key},
            ).scalar()
        )
        if not acquired:
            raise AgentRunBusyError("Agent run is already being modified")
        try:
            yield
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": key},
            )
