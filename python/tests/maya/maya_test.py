"""Support functionality for running tests in Maya."""
from collections.abc import Iterator
from contextlib import contextmanager
import tempfile
import unittest
from unittest.mock import patch


@contextmanager
def mayaAppDirPatched() -> Iterator[None]:
    """Redirects Maya away from any application data that the testing user has."""
    with tempfile.TemporaryDirectory() as tempdirPath:
        with patch.dict("os.environ", {"MAYA_APP_DIR": tempdirPath}):
            yield


@contextmanager
def mayaInitialized() -> Iterator[None]:
    """Ensures that maya.standalone is initialized and uninitialized properly."""
    import maya.standalone  # pylint: disable=import-outside-toplevel

    maya.standalone.initialize()

    try:
        yield
    finally:
        try:
            maya.standalone.uninitialize()
        except:  # pylint: disable=bare-except
            # All exceptions are caught per instruction from Autodesk
            pass


class MayaTestProgram(unittest.TestProgram):
    """Discovers and runs tests for Maya."""

    def runTests(self) -> None:
        """Runs the discovered unit tests."""
        with mayaAppDirPatched(), mayaInitialized():
            super().runTests()


main = MayaTestProgram


if __name__ == "__main__":
    main(module=None)
