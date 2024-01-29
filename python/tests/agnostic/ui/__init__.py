"""Tests for UI modules that don't pertain to a particular DCC."""
from PySide2 import QtCore
from PySide2.QtWidgets import QApplication


# Ensure that a QApplication is running
if not QApplication.instance():
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    QApplication([])
