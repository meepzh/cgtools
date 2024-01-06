"""Simple configuration system that combines configuration files from various levels.

Configurations exist per package (e.g.: cgtools) per file (e.g.: logging) and receive
contributions as follows, from the highest priority to the lowest:

* User
* Current working directory
* Current working directory's parent, and its parent, with decreasing priority, etc.
* The Rez package configuration directory, if it exists

Packages must store their base configurations in the ``config`` directory in the package
root directory.

Working directory configurations are expected to be located in a ``.config`` directory.
The first subdirectory indicates the project name, and then configuration files can be
located there.

User configurations for Linux are expected in the ``$XDG_CONFIG_HOME`` directory. If
``XDG_CONFIG_HOME`` does not define a path, then ``~/.config`` is used. Configurations
for Windows users are expected in ``%APPDATA%``. For both operating systems, the first
subdirectory indicates the project name, and then the configuration files can be located
there.

Configuration files are expected to be JSON files with the ``.json`` file extension.
JSON was chosen to minimize dependencies on other packages in spite of the usability
issues, while also ensuring consistent internal layering support. There is planned
support for TOML for the same reasons.

So as an example, configurations may be layered like so:

* ``$XDG_CONFIG_HOME/cgtools/logging.json``
* ``/mnt/Workspace/projectName/.config/cgtools/logging.json`` or
  ``\\\\workspace\\projectName\\.config\\cgtools\\logging.json``
* ``/mnt/Workspace/.config/cgtools/logging.json`` or
  ``\\\\workspace\\.config\\cgtools\\logging.json``
* ``$XDG_CONFIG_HOME/cgtools/logging.json`` or ``%APPDATA%\\cgtools\\logging.json``
* ``$REZ_CGTOOLS_ROOT/config/logging.json``

Configurations may be retrieved like so:
    ::

        from cgtools.agnostic.layered_config import LayeredConfig
        config_dict = LayeredConfig("cgtools").get_config("logging")
"""
import json
import logging
import os
import pathlib
from typing import Any

import rez.status


logger = logging.getLogger(__name__)


class LayeredConfig:
    """Retrieves the configuration for a package.

    Args:
        package: The name of the package.
    """

    def __init__(self, package: str):
        super().__init__()
        self._package = package

        # Config dirs are stored from highest to lowest priority
        self._config_dirs: list[pathlib.Path] = []
        self._cache_config_dirs()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.package}')"

    def get_config(self, name: str) -> dict[Any, Any]:
        """Retrieves the package configuration of the specified name.

        Args:
            The name of the specific configuration.

        Returns:
            The configuration dictionary.
        """
        config_sum = {}

        for config_dir in reversed(self._config_dirs):
            config_path = config_dir.joinpath(f"{name}.json")
            logger.debug("Searching for config file at: %s", config_path)
            if not config_path.is_file():
                continue

            with config_path.open() as config_file:
                config = json.load(config_file)
            config_sum.update(config)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("- Loaded %d bytes", config_path.stat().st_size)

        return config_sum

    @property
    def package(self) -> str:
        """Returns the name of the package for this config.

        Returns:
            The name.
        """
        return self._package

    def _cache_config_dirs(self):
        """Searches for any available config directories and stores them in the
        instance.
        """
        # Find user config dir
        user_config_dir = self._find_user_config_dir()
        if user_config_dir:
            self._config_dirs.append(user_config_dir)

        # Find working-directory-based config dir
        work_dirs = [pathlib.Path.cwd()]
        work_dirs += list(work_dirs[0].parents)
        for work_dir in work_dirs:
            work_config_dir = pathlib.Path(work_dir, ".config", self.package)
            logger.debug("Searching for work config directory in: %s", work_config_dir)
            if work_config_dir.is_dir():
                self._config_dirs.append(work_config_dir)

        # Find package config dir
        context = rez.status.status.context
        package = context.get_resolved_package(self.package)
        package_config_dir = pathlib.Path(package.root, "config")
        logger.debug(
            "Searching for package config directory in: %s", package_config_dir
        )
        if package_config_dir.is_dir():
            self._config_dirs.append(package_config_dir)

        # Log final dirs
        logger.debug("Found the following config directories:")
        for config_dir in self._config_dirs:
            logger.debug("- %s", config_dir)

        # Warn if no paths were found
        if not self._config_dirs:
            logger.warning("No config directories found for package '%s'", self.package)

    def _find_user_config_dir(self) -> pathlib.Path | None:
        """Searches for the user configuration directory.

        Returns:
            The directory path, if found.
        """
        env_var = os.getenv("APPDATA")
        if env_var:
            path = pathlib.Path(env_var, self.package)
            logger.debug("Searching for user config directory in: %s", path)
            if path.is_dir():
                return path

        env_var = os.getenv("XDG_CONFIG_HOME")
        if env_var:
            path = pathlib.Path(env_var, self.package)
            logger.debug("Searching for user config directory in: %s", path)
            if path.is_dir():
                return path

        path = pathlib.Path.home().joinpath(".config").joinpath(self.package)
        logger.debug("Searching for user config directory in: %s", path)
        if path.is_dir():
            return path

        return None
