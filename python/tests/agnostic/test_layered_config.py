"""Tests ``layered_config``."""
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest.mock import (
    Mock,
    patch,
)

from cgtools.agnostic.layered_config import LayeredConfig


class TestLayeredConfig(unittest.TestCase):
    """Tests ``LayeredConfig``."""

    # The configuration to use for testing
    CONFIG_NAME = "test_config"

    # The package to use for testing
    PACKAGE_NAME = "test_package"

    # The base configuration directory
    test_dir: pathlib.Path | None = None

    _original_cwd = ""
    _resolved_package_patcher: unittest.mock._patch | None = None

    @classmethod
    def setUpClass(cls):
        """Prepares a temporary directory with the configuration files in order to help
        prevent ``LayeredConfig`` from searching unintended directories.
        """
        # pylint: disable-next=consider-using-with
        cls.test_dir = tempfile.TemporaryDirectory()

        # Copy the supporting files
        support_path = pathlib.Path(__file__)
        support_path = support_path.parent.joinpath(f"{support_path.stem}_files")
        shutil.copytree(support_path, cls.test_dir.name, dirs_exist_ok=True)

        # Set the current working directory
        cls._original_cwd = os.getcwd()
        os.chdir(pathlib.Path(cls.test_dir.name, "workspace", "projectName"))

        # Create a mock package
        root_path = pathlib.Path(cls.test_dir.name, f"{cls.PACKAGE_NAME}_root")
        mock_package = Mock()
        mock_package.root = str(root_path)
        cls._resolved_package_patcher = unittest.mock.patch(
            "rez.resolved_context.ResolvedContext.get_resolved_package",
            return_value=mock_package,
        )
        cls._resolved_package_patcher.start()

    @classmethod
    def tearDownClass(cls):
        """Cleans up the directory changes."""
        cls._resolved_package_patcher.stop()
        os.chdir(cls._original_cwd)
        cls.test_dir.cleanup()

    def assert_config_values(self):
        """Confirms that the layered configuration values are correct."""
        config = LayeredConfig(self.PACKAGE_NAME).get_config(self.CONFIG_NAME)
        for test in (
            "user",
            "user_overrides_project",
            "user_overrides_workspace",
            "user_overrides_package",
            "project",
            "project_overrides_workspace",
            "project_overrides_package",
            "workspace",
            "workspace_overrides_package",
            "package",
        ):
            self.assertEqual(test, config.get(test))
            self.assertEqual(test, config["layer"].get(test))

    def test_repr(self):
        """Tests ``LayeredConfig.__repr__``."""
        config = LayeredConfig(self.PACKAGE_NAME)
        self.assertEqual(f"LayeredConfig('{self.PACKAGE_NAME}')", repr(config))

    def test_empty_config(self):
        """Tests ``LayeredConfig.get_config`` where the config name is non-existent."""
        layered_config = LayeredConfig(self.PACKAGE_NAME)
        config = layered_config.get_config("empty_config")
        self.assertEqual({}, config)

    def test_get_config_user_appdata(self):
        """Tests ``LayeredConfig.get_config`` where the user config is located in
        ``%APPDATA%``.
        """
        appdata_path = str(pathlib.Path(self.test_dir.name, "test_home", ".config"))
        with patch.dict(
            "os.environ",
            {
                "APPDATA": appdata_path,
                "HOME": "",
                "USERPROFILE": "",
                "XDG_CONFIG_HOME": "",
            },
        ):
            self.assert_config_values()

    def test_get_config_user_home(self):
        """Tests ``LayeredConfig.get_config`` where the user config is located in
        ``$HOME/.config`` on Unix or ``%USERPROFILE%/.config`` on Windows.
        """
        home_path = str(pathlib.Path(self.test_dir.name, "test_home"))
        with patch.dict(
            "os.environ",
            {
                "APPDATA": "",
                "HOME": home_path,
                "USERPROFILE": home_path,
                "XDG_CONFIG_HOME": "",
            },
        ):
            self.assert_config_values()

    def test_get_config_user_xdg_config_home(self):
        """Tests ``LayeredConfig.get_config`` where the user config is located in
        ``$XDG_CONFIG_HOME``.
        """
        xdg_config_home_path = str(
            pathlib.Path(self.test_dir.name, "test_home", ".config")
        )
        with patch.dict(
            "os.environ",
            {
                "APPDATA": "",
                "HOME": "",
                "USERPROFILE": "",
                "XDG_CONFIG_HOME": xdg_config_home_path,
            },
        ):
            self.assert_config_values()

    def test_package(self):
        """Tests ``LayeredConfig.package``."""
        config = LayeredConfig(self.PACKAGE_NAME)
        self.assertEqual(self.PACKAGE_NAME, config.package)


if __name__ == "__main__":
    unittest.main()
