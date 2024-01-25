"""Reloads Python modules to aid in development.
"""
from contextlib import contextmanager
import importlib
import logging
import pathlib
import sys

from PySide2 import (
    QtCore,
    QtGui,
    QtWidgets,
)
import rez.status

from cgtools.agnostic.ui import ui_loader


EXTERNAL_ROLE = QtCore.Qt.UserRole


logger = logging.getLogger(__name__)


class ModuleReloaderWidget(QtWidgets.QWidget):
    """Display for modules that can be reloaded in the widget.

    Example:
        ::

            widget = cgtools.agnostic.ui.module_reloader.ModuleReloaderWidget()
            widget.show()
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        f: QtCore.Qt.WindowFlags = QtCore.Qt.WindowFlags(),
    ):
        super().__init__(parent=parent, f=f)
        loader = ui_loader.UiLoader()
        loader.loadUi(self)

        self.sourceModel = QtGui.QStandardItemModel(parent=self)

        # Set up proxy model
        self.proxyModel = ModuleProxyModel(parent=self)
        self.proxyModel.setSourceModel(self.sourceModel)
        self.proxyModel.sort(0)
        self.moduleList.setModel(self.proxyModel)

        # Use a second selection model to keep track of selections while filtering
        # deselects hidden items
        self.fullSelectionModel = ReverseProxySelectionModel(
            self.sourceModel,
            self.proxyModel,
            self.moduleList.selectionModel(),
            parent=self,
        )

        # Convenience structure for tracking what has been added or removed from
        # sys.modules
        self._modules: set[str] = set()

        # Maps Rez package bases to whether the packages are external
        self._rezPackageIsExternal: dict[pathlib.Path, bool] = {}
        # Locations where Rez packages reside, to be used as a first pass filter
        self._rezLocations: list[pathlib.Path] = []
        self._cacheRezData()

        # Update UI
        self.filterPatternChanged(self.filterPatternLineEdit.text())
        self.showExternalPackages(self.showExternalCheckBox.checkState())
        self.refresh()

    @QtCore.Slot(str)
    def filterPatternChanged(self, pattern: str):
        """Updates which items are prevented from appearing in the module list.

        Args:
            pattern: The wildcard-style pattern to use. A wildcard is automatically
                appended to the provided pattern.
        """
        with self.fullSelectionModel.selectionPreserved():
            pattern += "*"
            self.proxyModel.setFilterRegularExpression(
                QtCore.QRegularExpression.wildcardToRegularExpression(pattern + "*")
            )
            logger.debug("Changed filter pattern to %s", pattern)

    @QtCore.Slot()
    def refresh(self):
        """Updates the module list with the modules available for reloading."""
        modules = set(sys.modules)

        for moduleToAdd in modules - self._modules:
            if not hasattr(sys.modules[moduleToAdd], "__file__"):
                # This is a built-in module
                continue
            self._addModule(moduleToAdd)

        for moduleToRemove in self._modules - modules:
            matches = self.sourceModel.findItems(moduleToRemove)
            if matches:
                row = matches[0].row()
                success = self.sourceModel.removeRow(row)
                if success:
                    logger.debug(
                        "Removed module '%s' at row %d from module list",
                        moduleToRemove,
                        row,
                    )
                else:
                    logger.warning(
                        "Could not remove module '%s' at row %d from module list",
                        moduleToRemove,
                        row,
                    )
            else:
                logger.warning(
                    "Module '%s' was not found in the module list and cannot be "
                    "removed",
                    moduleToRemove,
                )

        self._modules = modules

    @QtCore.Slot()
    def reload(self):
        """Reloads the selected modules."""
        for index in self.moduleList.selectedIndexes():
            index = self.proxyModel.mapToSource(index)
            moduleName = self.sourceModel.data(index)
            importlib.reload(sys.modules[moduleName])
            logger.debug("Reloaded module '%s'", moduleName)

    @QtCore.Slot(int)
    def showExternalPackages(self, checkState: QtCore.Qt.CheckState | int):
        """Updates the filter's behavior with regards to external packages as described
        in ``ModuleProxyModel``.

        Args:
            checkState: Enable the filtering unless ``QtCore.Qt.Unchecked``
                (which has a value of 0) is provided.
        """
        with self.fullSelectionModel.selectionPreserved():
            showState = checkState != QtCore.Qt.Unchecked
            logger.debug("Showing external packages: %r", showState)
            self.proxyModel.showExternalPackages(showState)

    @QtCore.Slot(QtCore.QPoint)
    def showModuleListContextMenu(self, pos: QtCore.QPoint):
        """Displays a collection of contextual actions pertaining to the module list.

        Args:
            pos: The position with which to open the menu relative to the module list.
        """
        contextMenu = QtWidgets.QMenu(self.moduleList)

        if self.proxyModel.rowCount() < self.sourceModel.rowCount():
            selectAllText = "Select All Filtered"
            deselectAllText = "Deselect All Filtered"
        else:
            selectAllText = "Select All"
            deselectAllText = "Deselect All"

        selectAllAction = contextMenu.addAction(selectAllText)
        selectAllAction.triggered.connect(self.moduleList.selectAll)

        deselectAllAction = contextMenu.addAction(deselectAllText)
        deselectAllAction.triggered.connect(self.moduleList.clearSelection)

        contextMenu.exec_(self.moduleList.mapToGlobal(pos))

    def _addModule(self, moduleName: str):
        """Adds the given module to the list of modules.

        Args:
            moduleName: The name of the module.
        """
        item = QtGui.QStandardItem(moduleName)

        modulePath = pathlib.Path(str(sys.modules[moduleName].__file__))
        item.setToolTip(
            f"<p style='white-space: nowrap;'><b>{moduleName}</b>:<br/>{modulePath}</p>"
        )

        isExternal = all(
            location not in modulePath.parents for location in self._rezLocations
        )
        if not isExternal:
            for packageBase, packageIsExternal in self._rezPackageIsExternal.items():
                if packageBase in modulePath.parents:
                    isExternal = packageIsExternal
                    break
        item.setData(isExternal, role=EXTERNAL_ROLE)

        self.sourceModel.appendRow(item)

    def _cacheRezData(self):
        """Processes the Rez environment and stores package information."""
        for variant in rez.status.status.context.resolved_packages:
            location = pathlib.Path(variant.resource.location)
            if location not in self._rezLocations:
                self._rezLocations.append(location)

            reason = ""
            if getattr(variant, "external", False):
                reason = "package has 'external' attribute set"
            elif getattr(variant, "_native", False):
                reason = "package has '_native' attribute set"
            elif not variant.is_local:
                reason = "package was not installed locally"
            elif variant.name in ("python", "rez"):
                reason = "package name"
            isExternal = bool(reason)

            self._rezPackageIsExternal[pathlib.Path(variant.base)] = isExternal
            logger.debug(
                "Cached Rez package '%s' (external: %r%s, path: %s)",
                variant.name,
                isExternal,
                f", reason: {reason}" if reason else "",
                variant.base,
            )


class ModuleProxyModel(QtCore.QSortFilterProxyModel):
    """Custom sorting and filtering proxy model that also accounts for whether the
    module item is external.

    "External" can either indicate an origin from a Rez package that is marked with the
    "external" attribute or an origin coming from outside the Rez ecosystem (e.g.: from
    the operating system).

    The "external" attribute must be stored on the source model using ``EXTERNAL_ROLE``
    as the item data role.
    """

    def __init__(self, parent: QtCore.QObject = None):
        super().__init__(parent=parent)
        self._showExternal = False

    def filterAcceptsRow(
        self, sourceRow: int, sourceParent: QtCore.QModelIndex
    ) -> bool:
        """Overrides the default behavior when external filtering is enabled and an
        item is marked as external.
        """
        index = self.sourceModel().index(
            sourceRow, self.filterKeyColumn(), sourceParent
        )
        if (
            self.sourceModel().data(index, role=EXTERNAL_ROLE)
            and not self._showExternal
        ):
            return False
        return super().filterAcceptsRow(sourceRow, sourceParent)

    def showExternalPackages(self, on: bool):
        """Updates whether items marked as external will be shown.

        Args:
            on: Whether to show external items.
        """
        self._showExternal = on
        self.invalidateFilter()


class ReverseProxySelectionModel(QtCore.QItemSelectionModel):
    """Preserves selection from the proxy model in spite of selection loss during
    filtering.

    Args:
        model: The model to store selections for.
        proxy: The proxy model used for filtering.
        proxySelectionModel: The selection model used on the proxy model.
        parent: The owner of this object.
    """

    def __init__(
        self,
        model: QtCore.QAbstractItemModel,
        proxy: QtCore.QAbstractProxyModel,
        proxySelectionModel: QtCore.QItemSelectionModel,
        parent: QtCore.QObject | None = None,
    ):
        super().__init__(model, parent=parent)
        self._blockUpdates = False
        self._proxy = proxy
        self._proxySelectionModel = proxySelectionModel

        self.proxySelectionModel().selectionChanged.connect(self.mirrorSelectionChange)

    def proxy(self) -> QtCore.QAbstractProxyModel:
        """Returns the stored proxy model.

        Providing the proxy model through a regular method like this mirrors how
        ``QItemSelectionModel`` provides access to the source model with ``model()``.

        Returns:
            The proxy.
        """
        return self._proxy

    def proxySelectionModel(self) -> QtCore.QItemSelectionModel:
        """Returns the stored proxy selection model.

        Providing the proxy selection model through a regular method like this mirrors
        how ``QItemSelectionModel`` provides access to the source model with
        ``model()``.

        Returns:
            The proxy selection model.
        """
        return self._proxySelectionModel

    @QtCore.Slot(QtCore.QItemSelection, QtCore.QItemSelection)
    def mirrorSelectionChange(
        self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection
    ):
        """Copies the proxy selection changes onto this model when selection changes are
        not blocked.

        Args:
            selected: The items being selected.
            deselected: The items being deselected.
        """
        if self._blockUpdates:
            logger.debug("Blocked selection changes from being mirrored")
            return
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Mirroring selection changes: +%d/-%d items",
                len(selected.indexes()),
                len(deselected.indexes()),
            )

        selected = self.proxy().mapSelectionToSource(selected)
        deselected = self.proxy().mapSelectionToSource(deselected)

        self.select(selected, self.SelectionFlag.Select)
        self.select(deselected, self.SelectionFlag.Deselect)

    @contextmanager
    def selectionPreserved(self):
        """Prevents selection change signals from modifying this model and reapplies
        unhidden selections to the proxy model.
        """
        logger.debug("Turning on selection preservation")
        try:
            self._blockUpdates = True
            yield

            selection = self.selection()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Re-selecting %d items", len(selection.indexes()))

            selection = self.proxy().mapSelectionFromSource(selection)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Mapped re-selection to %d items", len(selection.indexes())
                )

            self.proxySelectionModel().select(
                selection, self.SelectionFlag.ClearAndSelect
            )

        finally:
            logger.debug("Turning off selection preservation")
            self._blockUpdates = False
