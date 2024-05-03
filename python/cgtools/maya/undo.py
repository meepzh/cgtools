"""Helper utilities for manipulating the Maya undo queue."""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import wraps
from typing import (
    Any,
    Callable,
)

from maya import cmds


def undoChunk(name: str) -> Callable:
    """Opens and closes an undo chunk around the decorated function with the given name.

    Args:
        name: The name of the undo chunk.

    Returns:
        The wrapped function.
    """

    def undoChunkFactory(func: Callable) -> Callable:
        """Creates a wrapper function to manange the undo chunk around the provided
        function.

        Args:
            func: The function to decorate.

        Returns:
            The wrapped function.
        """

        @wraps(func)
        def undoChunkWrapper(*args, **kwargs) -> Any:
            """Opens and closes an undo chunk around the wrapped function.

            Args:
                args: The arguments to pass to the wrapped function.
                kwargs: The keyword arguments to pass to the wrapped function.

            Returns:
                The result from the wrapped function.
            """
            with undoChunkOpened(name):
                return func(*args, **kwargs)

        return undoChunkWrapper

    return undoChunkFactory


@contextmanager
def undoChunkOpened(name: str) -> Iterator[None]:
    """Opens and closes an undo chunk during the context.

    Args:
        name: The name of the undo chunk.
    """
    undoEnabled = cmds.undoInfo(query=True, state=True)
    if undoEnabled:
        cmds.undoInfo(openChunk=True, chunkName=name)
    try:
        yield
    finally:
        if undoEnabled:
            cmds.undoInfo(closeChunk=True)
