"""Isolated rendering appearances, independent of accounts and persistence."""
from contextvars import ContextVar
from typing import Callable, TypeVar

from cosmetics.catalog import Appearance

_CURRENT: ContextVar[Appearance] = ContextVar('casino_render_appearance', default=Appearance())
_Result = TypeVar('_Result')


def current_appearance() -> Appearance:
    """The immutable appearance for this render, task, or worker thread."""
    return _CURRENT.get()


def run_with_appearance(appearance: Appearance, operation: Callable[..., _Result], *args, **kwargs) -> _Result:
    """Run a synchronous renderer with an appearance and always restore context.

    Call this helper inside ``asyncio.to_thread`` for Pillow work. It performs
    no database lookup and never changes a process-wide active theme.
    """
    if not isinstance(appearance, Appearance):
        raise TypeError('A render requires an immutable Appearance')
    token = _CURRENT.set(appearance)
    try:
        return operation(*args, **kwargs)
    finally:
        _CURRENT.reset(token)
