"""Adds ANSI colors to logging."""
import logging


class ColoredLogFormatter(logging.Formatter):
    """Logging formatter that changes the terminal colors of the log messages depending
    on the log record level.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Formats the record as is typically done, then adds coloring to the message."""
        formatted_message = super().format(record)
        return self.getLevelColor(record.levelno) + formatted_message + "\033[0m"

    @staticmethod
    def getLevelColor(level: int) -> str:
        """Returns the ANSI code to be used for the given log level.

        Args:
            level: The log level.

        Returns:
            The code.
        """
        match level:
            case logging.DEBUG:
                return "\033[0;34m"
            case logging.WARNING:
                return "\033[0;33m"
            case logging.ERROR:
                return "\033[0;31m"
            case logging.CRITICAL:
                return "\033[1;31m"
            case _:
                return ""
