"""Customize PySide UI loading behavior."""
import pathlib
import sys

from PySide2 import (
    QtCore,
    QtUiTools,
    QtWidgets,
)


class UiLoader(QtUiTools.QUiLoader):
    """Generates the user interface for a widget, as specified by its UI file.

    Example::

        from PySide2 import QtWidgets

        class CustomWidget(QtWidgets.QWidget):
            pass

        class TargetWidget(QtWidgets.QWidget):
            def __init__(self):
                super().__init__()
                loader = UiLoader()
                loader.registerCustomWidget(CustomWidget)
                loader.loadUi(self)
    """

    def __init__(self) -> None:
        super().__init__()
        self._target: QtWidgets.QWidget | None = None

    def createWidget(
        self, className: str, parent: QtWidgets.QWidget = None, name: str = ""
    ) -> QtWidgets.QWidget:
        """Extends ``QUiLoader`` to attach UI widgets to the target widget."""
        if parent is None and self._target is not None:
            # This is the root widget, so use the target if it's available
            return self._target

        widget = super().createWidget(className, parent, name)
        if self._target is not None:
            setattr(self._target, name, widget)
        return widget

    def loadUi(
        self, target: QtWidgets.QWidget, uiPathStr: str = ""
    ) -> QtWidgets.QWidget:
        """Finds the UI file and attaches it to the target widget.

        Args:
            target: The widget to attach to.
            uiPath: The path to the UI file. Defaults to the widget's module file name,
                but with the ``.ui`` file extension.

        Returns:
            The widget generated from the UI file.
        """
        if not uiPathStr:
            targetModule = sys.modules[target.__class__.__module__]
            uiPath = pathlib.Path(str(targetModule.__file__))
            uiPath = uiPath.resolve().with_suffix(".ui")
            uiPathStr = str(uiPath)

        self._target = target
        try:
            widget = self.load(uiPathStr)
        finally:
            self._target = None
        QtCore.QMetaObject.connectSlotsByName(target)
        return widget
