"""Persistence step: one place for commit, rollback, and DB-error mapping."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from core.exceptions import ConflictException
from core.logger import logger

_DEPTH_KEY = "transaction_depth"


@contextmanager
def transaction(session: Session) -> Generator[Session]:
    """Run a block of writes as one transaction.

    - The outermost block commits on normal exit; nested blocks join it.
    - Any exception rolls back the whole transaction and is re-raised.
    - IntegrityError (unique or foreign-key violation) becomes ConflictException.
    """
    depth = int(session.info.get(_DEPTH_KEY, 0))
    session.info[_DEPTH_KEY] = depth + 1
    try:
        yield session
        if depth == 0:
            session.commit()
    except IntegrityError as e:
        session.rollback()
        logger.warning(f"Integrity error, mapped to conflict: {e.orig}")
        raise ConflictException("Conflicts with existing data") from e
    except Exception:
        session.rollback()
        raise
    finally:
        session.info[_DEPTH_KEY] = depth
