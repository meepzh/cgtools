"""Tests ``module_reloader``."""
from collections.abc import (
    Iterable,
    Iterator,
    MutableMapping,
)
from contextlib import contextmanager
import pathlib
import sys
from typing import (
    Any,
    TypeVar,
)
import unittest
from unittest.mock import (
    Mock,
    patch,
)

from PySide2 import (
    QtCore,
    QtGui,
    QtWidgets,
)
from PySide2.QtTest import QTest

from cgtools.agnostic.ui.module_reloader import ModuleReloaderWidget


class TestModuleReloaderWidget(unittest.TestCase):
    """Tests ``ModuleReloaderWidget``."""

    def test_refreshButton(self):
        """Tests that ``ModuleReloaderWidget.refreshButton`` refreshes the list of
        modules available.
        """
        # Set a reduced list of modules
        modules = ["internal", "internal.foo", "internal.bar"]
        with self._modulesReplaced(modules):
            widget = ModuleReloaderWidget()
        self.assertEqual(self._getDisplayedModules(widget), sorted(modules))

        # Check if an updated list of modules is picked up
        modules = ["internal", "internal.bar", "internal.baz"]
        with self._modulesReplaced(modules):
            QTest.mouseClick(widget.refreshButton, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), sorted(modules))

    def test_showExternalCheckBox(self):
        """Tests that ``ModuleReloaderWidget.showExternalPackages`` toggles the display
        of external packages in the modules list.
        """
        # Set a mix of external and internal modules
        modules = sorted(
            ["external", "internal", "internal.foo", "native", "unpackaged"]
        )
        internalModules = [
            module for module in modules if module.startswith("internal")
        ]
        with self._modulesReplaced(modules):
            widget = ModuleReloaderWidget()

        # Ensure that the external checkbox is ticked off
        if widget.showExternalCheckBox.checkState() != QtCore.Qt.Unchecked:
            QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)

        self.assertEqual(self._getDisplayedModules(widget), internalModules)

        # Check if the full list is now displayed
        QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), modules)

        # Check that ticking off the checkbox works as well
        QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), internalModules)

    def test_filterPatternLineEdit(self):
        """Tests that ``ModuleReloaderWidget.filterPatternLineEdit`` filters the list
        of modules.
        """
        # Confirm that all modules are shown
        modules = sorted(
            ["internal.foo1", "internal.foo2", "internal.bar1", "internal.bar2"]
        )
        fooModules = [module for module in modules if module.startswith("internal.foo")]
        with self._modulesReplaced(modules):
            widget = ModuleReloaderWidget()
        self.assertEqual(self._getDisplayedModules(widget), modules)

        # Confirm that all modules still appear when using a common filter
        QTest.keyClicks(widget.filterPatternLineEdit, "internal")
        self.assertEqual(self._getDisplayedModules(widget), modules)

        # Test that a more restrictive filter does filter the packages
        QTest.keyClicks(widget.filterPatternLineEdit, ".foo")
        self.assertEqual(self._getDisplayedModules(widget), fooModules)

        # Test an additional wildcard character
        QTest.keyClick(widget.filterPatternLineEdit, "*")
        self.assertEqual(self._getDisplayedModules(widget), fooModules)

        # Clear the filter and confirm no filtering is done
        for _ in range(30):
            QTest.keyClick(widget.filterPatternLineEdit, QtCore.Qt.Key_Backspace)
        self.assertEqual(self._getDisplayedModules(widget), modules)

        # Test that a single wildcard has no filtering effect
        QTest.keyClick(widget.filterPatternLineEdit, "*")
        self.assertEqual(self._getDisplayedModules(widget), modules)
        QTest.keyClick(widget.filterPatternLineEdit, QtCore.Qt.Key_Backspace)

        # Test a filter that won't match anything
        QTest.keyClicks(widget.filterPatternLineEdit, "external")
        self.assertEqual(self._getDisplayedModules(widget), [])

    def test_contextMenu_selection(self):
        """Tests that ``ModuleReloaderWidget.moduleList``'s context menu selection
        actions behave correctly.
        """
        modules = sorted(["internal.foo1", "internal.foo2", "internal.bar", "external"])
        fooModules = [module for module in modules if module.startswith("internal.foo")]
        internalModules = [
            module for module in modules if module.startswith("internal")
        ]
        with self._modulesReplaced(modules):
            widget = ModuleReloaderWidget()

        # Ensure that the external checkbox is ticked on so all modules are shown
        if widget.showExternalCheckBox.checkState() != QtCore.Qt.Checked:
            QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), modules)

        # Confirm that nothing is selected by default
        self.assertEqual(self._getSelectedModules(widget), [])

        # Test Select All
        self._findContextMenuAction(widget.moduleList, "selectAllAction").trigger()
        self.assertEqual(self._getSelectedModules(widget), modules)

        # Test Deselect All
        self._findContextMenuAction(widget.moduleList, "deselectAllAction").trigger()
        self.assertEqual(self._getSelectedModules(widget), [])

        # Apply the external package filter
        QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), internalModules)

        # Test Select All with external filter
        self._findContextMenuAction(widget.moduleList, "selectAllAction").trigger()
        self.assertEqual(self._getSelectedModules(widget), internalModules)

        # Check that the selection stays with the external filter removed
        QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), modules)
        self.assertEqual(self._getSelectedModules(widget), internalModules)

        # Reset with Deselect All
        self._findContextMenuAction(widget.moduleList, "deselectAllAction").trigger()
        self.assertEqual(self._getSelectedModules(widget), [])

        # Test with the filter pattern
        QTest.keyClicks(widget.filterPatternLineEdit, "internal.foo")
        self._findContextMenuAction(widget.moduleList, "selectAllAction").trigger()
        self.assertEqual(self._getSelectedModules(widget), fooModules)

        # Check that the selection stays with the pattern removed
        for _ in range(30):
            QTest.keyClick(widget.filterPatternLineEdit, QtCore.Qt.Key_Backspace)
        self.assertEqual(self._getDisplayedModules(widget), modules)
        self.assertEqual(self._getSelectedModules(widget), fooModules)

    def test_contextMenu_hideUnselected(self):
        """Tests that ``ModuleReloaderWidget.moduleList``'s context menu action for
        hiding unselected modules behaves correctly.
        """
        modules = sorted(
            ["internal.bar1", "internal.bar2", "internal.foo1", "internal.foo2"]
        )
        with self._modulesReplaced(modules):
            widget = ModuleReloaderWidget()

        # Select some of the items
        selectedModules = []
        for row in (0, 2, 3):
            index = widget.moduleList.model().index(row, 0)
            selectedModules.append(widget.moduleList.model().data(index))
            widget.moduleList.selectionModel().select(
                index, QtCore.QItemSelectionModel.Select
            )
        self.assertEqual(self._getDisplayedModules(widget), modules)
        self.assertEqual(self._getSelectedModules(widget), selectedModules)

        # Enable hiding unselected and confirm that hiding works
        self._findContextMenuAction(
            widget.moduleList, "toggleUnselectedAction"
        ).trigger()
        self.assertEqual(self._getDisplayedModules(widget), selectedModules)
        self.assertEqual(self._getSelectedModules(widget), selectedModules)

        # Deselect an item to check that hiding stays updated
        deselectIndex = widget.moduleList.model().index(
            widget.moduleList.model().rowCount() - 1, 0
        )
        selectedModules.remove(widget.moduleList.model().data(deselectIndex))
        widget.moduleList.selectionModel().select(
            deselectIndex, QtCore.QItemSelectionModel.Deselect
        )
        self.assertEqual(self._getDisplayedModules(widget), selectedModules)
        self.assertEqual(self._getSelectedModules(widget), selectedModules)

        # Disable hiding unselected and confirm that the selection stays
        self._findContextMenuAction(
            widget.moduleList, "toggleUnselectedAction"
        ).trigger()
        self.assertEqual(self._getDisplayedModules(widget), modules)
        self.assertEqual(self._getSelectedModules(widget), selectedModules)

    def test_selectionPreservation(self):
        """Tests that the module selection is temporarily affected by filtering. That
        is, when a filter is applied, only the selected items that pass the filter are
        known to be selected. But when the filter is removed, those previously selected
        items are re-selected.
        """
        # Set a mix of external and internal modules
        modules = sorted(
            ["external", "internal", "internal.foo", "native", "unpackaged"]
        )
        externalModules = [
            module for module in modules if not module.startswith("internal")
        ]
        internalModules = [
            module for module in modules if module.startswith("internal")
        ]
        with self._modulesReplaced(modules):
            widget = ModuleReloaderWidget()

        # Ensure that the external checkbox is ticked on so all modules are shown
        if widget.showExternalCheckBox.checkState() != QtCore.Qt.Checked:
            QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), modules)

        # Select all modules
        self._findContextMenuAction(widget.moduleList, "selectAllAction").trigger()
        self.assertEqual(self._getSelectedModules(widget), modules)

        # Reapply the external filter
        QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), internalModules)
        self.assertEqual(self._getSelectedModules(widget), internalModules)

        # Apply a filter pattern
        QTest.keyClicks(widget.filterPatternLineEdit, "internal.foo")
        self.assertEqual(self._getSelectedModules(widget), ["internal.foo"])

        # Enable hiding unselected to see if this impacts behavior
        self._findContextMenuAction(
            widget.moduleList, "toggleUnselectedAction"
        ).trigger()

        # Deselect internal.foo using Deselect All
        self._findContextMenuAction(widget.moduleList, "deselectAllAction").trigger()
        self.assertEqual(self._getDisplayedModules(widget), [])
        self.assertEqual(self._getSelectedModules(widget), [])

        # Disable hiding unselected
        self._findContextMenuAction(
            widget.moduleList, "toggleUnselectedAction"
        ).trigger()

        # Check that the selection was preserved with the pattern removed
        for _ in range(30):
            QTest.keyClick(widget.filterPatternLineEdit, QtCore.Qt.Key_Backspace)
        self.assertEqual(self._getDisplayedModules(widget), internalModules)
        self.assertEqual(self._getSelectedModules(widget), ["internal"])

        # Deselect all internal modules using Deselect All
        self._findContextMenuAction(widget.moduleList, "deselectAllAction").trigger()

        # Check that the selection on the external packages was preserved when the
        # external filter is removed
        QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), modules)
        self.assertEqual(self._getSelectedModules(widget), externalModules)

    @patch("importlib.reload")
    def test_reloadButton(self, reloadMock):
        """Tests that ``ModuleReloaderWidget.reloadButton`` reloads only the visibly
        selected modules.
        """
        # Set a mix of external and internal modules
        modules = sorted(
            ["external", "internal", "internal.foo", "native", "unpackaged"]
        )
        internalModules = [
            module for module in modules if module.startswith("internal")
        ]
        with self._modulesReplaced(modules):
            widget = ModuleReloaderWidget()

        # Ensure that the external checkbox is ticked on so all modules are shown
        if widget.showExternalCheckBox.checkState() != QtCore.Qt.Checked:
            QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), modules)

        # Select all modules
        self._findContextMenuAction(widget.moduleList, "selectAllAction").trigger()
        self.assertEqual(self._getSelectedModules(widget), modules)

        # Reapply the external filter
        QTest.mouseClick(widget.showExternalCheckBox, QtCore.Qt.LeftButton)
        self.assertEqual(self._getDisplayedModules(widget), internalModules)
        self.assertEqual(self._getSelectedModules(widget), internalModules)

        # Apply a filter pattern
        QTest.keyClicks(widget.filterPatternLineEdit, "internal.foo")
        self.assertEqual(self._getSelectedModules(widget), ["internal.foo"])

        # Although all modules were selected, reloading should only apply to the
        # visible selection
        with self._modulesReplaced(modules):
            QTest.mouseClick(widget.reloadButton, QtCore.Qt.LeftButton)
        reloadMock.assert_called_once()
        self.assertEqual(reloadMock.call_args[0][0].__name__, "internal.foo")

    def _findContextMenuAction(
        self, widget: QtWidgets.QWidget, name: str
    ) -> QtWidgets.QAction:
        """Opens the widget's context menu and searches for a QAction with the given
        name.

        Args:
            widget: The widget to open a context menu under.
            name: The Qt object name of the action.

        Returns:
            The action.
        """
        contextMenuEvent = QtGui.QContextMenuEvent(
            QtGui.QContextMenuEvent.Keyboard, QtCore.QPoint()
        )
        QtWidgets.QApplication.instance().sendEvent(widget, contextMenuEvent)
        actions = widget.findChildren(QtWidgets.QAction, name)
        if not actions:
            self.fail(f"Could not find a context menu action with the name '{name}'")
        return actions[0]

    @staticmethod
    def _getDisplayedModules(widget: ModuleReloaderWidget) -> list[str]:
        """Fetches the ordered list of items being displayed in the modules list.

        Args:
            widget: The widget from which to fetch the data.

        Returns:
            The ordered list of names.
        """
        model = widget.moduleList.model()
        names: list[str] = []

        for row in range(model.rowCount()):
            index = model.index(row, 0)
            name = model.data(index)
            names.append(name)

        return names

    @staticmethod
    def _getSelectedModules(widget: ModuleReloaderWidget) -> list[str]:
        """Fetches the list of displayed selected items in the modules list.

        Args:
            widget: The widget from which to fetch the data.

        Returns:
            The list of names.
        """
        model = widget.moduleList.model()
        names: list[str] = []

        for index in widget.moduleList.selectedIndexes():
            name = model.data(index)
            names.append(name)

        return names

    @staticmethod
    def _mockModule(name: str) -> tuple[Mock, Mock | None]:
        """Generates a mock module and a mock package with properties derived from the
        name.

        * A name starting with "external" will be marked as external
        * A name starting with "internal" will be marked as internal
          (i.e.: not external)
        * A name starting with "native" will be marked as _native
        * Any name not covered above will not be marked as a Rez package, in which case
          the generated package will be ``None``.

        Args:
            name: The name of the module to mock.

        Returns:
            The mocked module.
            The mocked package, if any.
        """
        module = Mock()
        package = None
        prefix = pathlib.Path("/")

        if (
            name.startswith("external")
            or name.startswith("internal")
            or name.startswith("native")
        ):
            package = Mock()
            package.name = name
            package.is_local = True

            prefix = prefix.joinpath("rez")
            package.resource.location = prefix

            if name.startswith("external"):
                package.external = True
            else:
                del package.external
            if name.startswith("native"):
                package._native = True  # pylint: disable=protected-access
            else:
                del package._native

        # Convert "a.b.c" to "/prefix?/a/b/c"
        basePath = prefix.joinpath(*(name.split(".")))
        module.__file__ = str(basePath.joinpath("__init__.py"))
        module.__name__ = name
        if package:
            package.base = str(basePath)

        return (module, package)

    @classmethod
    @contextmanager
    def _modulesReplaced(
        cls, names: Iterable[str]
    ) -> Iterator[tuple[MutableMapping, list[Mock]]]:
        """Patches sys.modules with the given modules and patches Rez to recognize any
        mocked Rez modules as modules.

        Args:
            names: The module names to patch in.

        Yields:
            The replacement of ``sys.modules``.
            The replaced Rez packages.
        """
        mapping = PatchedModuleMapping[str]()
        packages = []

        for name in names:
            module, package = cls._mockModule(name)
            mapping[name] = module
            if package:
                packages.append(package)

        mapping.setOriginal(sys.modules)
        modulesPatch = patch("sys.modules", mapping)

        packagesPatch = patch(
            "rez.resolved_context.ResolvedContext.resolved_packages", packages
        )

        try:
            yield (
                modulesPatch.start(),
                packagesPatch.start(),
            )
        finally:
            modulesPatch.stop()
            packagesPatch.stop()


K = TypeVar("K")


class PatchedModuleMapping(MutableMapping[K, Any]):
    """Custom dictionary that only reveals patched modules over iteration while also
    preserving direct access to system modules. This is necessary as regular modules may
    still be accessed for the duration of the patch.

    Args:
        modules: The modules to patch in.
        original: The original module mapping.
    """

    def __init__(
        self,
        modules: MutableMapping[K, Any] | None = None,
        original: MutableMapping[K, Any] | None = None,
    ) -> None:
        super().__init__()
        self._modules = modules or {}
        self._original = original or {}

    def __getitem__(self, index: K) -> Any:
        """If the index refers to a patched module, then the patched version is
        returned. Otherwise, access to the original is provided.

        Args:
            index: The key.

        Returns:
            The indexed value.
        """
        if index in self._modules:
            return self._modules[index]
        return self._original[index]

    def __setitem__(self, index: K, value: Any) -> None:
        """Sets the value for the given index onto both the patch dictionary and the
        original.

        Args:
            index: The key.
            value: The value to set at the key.
        """
        self._modules[index] = value
        self._original[index] = value

    def __delitem__(self, index: K):
        """Removes the given item on both the patch dictionary and the original. It's
        not clear if exceptions should be raised, so this version exits gracefully if
        the item cannot be found.

        Args:
            index: The key.
        """
        self._modules.pop(index, None)
        self._original.pop(index, None)

    def __iter__(self) -> Iterator[K]:
        """Iterates over the patch dictionary.

        Yields:
            Keys from the patch dictionary.
        """
        yield from self._modules

    def __len__(self) -> int:
        """Returns the length of the patch dictionary.

        Returns:
            The length.
        """
        return len(self._modules)

    def setOriginal(self, original: MutableMapping[K, Any]) -> None:
        """Stores a reference to the original dictionary.

        Args:
            original: The mapping to use as the original.
        """
        self._original = original


if __name__ == "__main__":
    unittest.main()
