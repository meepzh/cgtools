"""Tests ``config_enum``."""
import enum
import unittest

from maya import cmds

from cgtools.maya.config_enum import (
    ConfigEnum,
    ConfigVar,
)


class IntEnum(enum.IntEnum):
    """Helps test that int enums can be used, serialized, and deserialized."""

    ZERO_INT = 0
    ONE_INT = 1
    TWO_INT = 2
    THREE_INT = 3


class StrEnum(enum.Enum):
    """Helps test that string enums can be used, serialized, and deserialized.

    This is a partial backport of Python 3.11's ``StrEnum`` class.
    """

    FOO_STRING = "foo"
    BAR_STRING = "bar"
    BAZ_STRING = "baz"

    def __str__(self):
        return self.value


class Config(ConfigEnum):
    """A configuration that contains a variety of variable types to test with."""

    FLOAT = ConfigVar(1.23)
    INT = ConfigVar(123)
    STRING = ConfigVar("foobar")
    FLOAT_ARRAY = ConfigVar([0.5, 1, 2.5])
    INT_ARRAY = ConfigVar([1, 2, 5, 10, 25, 50])
    STRING_ARRAY = ConfigVar(["foo", "bar"])
    BOOL = ConfigVar(True, serialize=int)  # Equivalent to 1
    INT_ENUM = ConfigVar(IntEnum.ONE_INT, serialize=int)  # Equivalent to True
    STRING_ENUM = ConfigVar(StrEnum.BAR_STRING, serialize=str)


class TestConfigEnum(unittest.TestCase):
    """Tests ``ConfigEnum``."""

    @classmethod
    def setUpClass(cls):
        """Store information to ensure a clean test environment."""
        cls.existingVars = set(cmds.optionVar(list=True))

    def tearDown(self):
        """Removes any new variables that were stored."""
        newVars = set(cmds.optionVar(list=True)) - self.existingVars
        for var in newVars:
            cmds.optionVar(remove=var)

    def test_name(self):
        """Tests ``ConfigEnum.name``. It may seem unnecessary to test every single
        config enum, but there have been strange results in the other test functions.
        """
        self.assertEqual("FLOAT", Config.FLOAT.name)
        self.assertEqual("INT", Config.INT.name)
        self.assertEqual("STRING", Config.STRING.name)
        self.assertEqual("FLOAT_ARRAY", Config.FLOAT_ARRAY.name)
        self.assertEqual("INT_ARRAY", Config.INT_ARRAY.name)
        self.assertEqual("STRING_ARRAY", Config.STRING_ARRAY.name)
        self.assertEqual("BOOL", Config.BOOL.name)
        self.assertEqual("INT_ENUM", Config.INT_ENUM.name)
        self.assertEqual("STRING_ENUM", Config.STRING_ENUM.name)

    def test_variable(self):
        """Tests ``ConfigEnum.variable``. It may seem unnecessary to test every single
        config enum, but there have been strange results in the other test functions.
        """
        self.assertEqual("test_config_enum_float", Config.FLOAT.variable)
        self.assertEqual("test_config_enum_int", Config.INT.variable)
        self.assertEqual("test_config_enum_string", Config.STRING.variable)
        self.assertEqual("test_config_enum_float_array", Config.FLOAT_ARRAY.variable)
        self.assertEqual("test_config_enum_int_array", Config.INT_ARRAY.variable)
        self.assertEqual("test_config_enum_string_array", Config.STRING_ARRAY.variable)
        self.assertEqual("test_config_enum_bool", Config.BOOL.variable)
        self.assertEqual("test_config_enum_int_enum", Config.INT_ENUM.variable)
        self.assertEqual("test_config_enum_string_enum", Config.STRING_ENUM.variable)

    def test_getValue_emptyStore(self):
        """Tests ``ConfigEnum.getValue`` when no value is stored, so the default must
        be returned.
        """
        self.assertEqual(1.23, Config.FLOAT.getValue())
        self.assertEqual(123, Config.INT.getValue())
        self.assertEqual("foobar", Config.STRING.getValue())
        self.assertEqual([0.5, 1, 2.5], Config.FLOAT_ARRAY.getValue())
        self.assertEqual([1, 2, 5, 10, 25, 50], Config.INT_ARRAY.getValue())
        self.assertEqual(["foo", "bar"], Config.STRING_ARRAY.getValue())
        self.assertIs(True, Config.BOOL.getValue())
        self.assertEqual(IntEnum.ONE_INT, Config.INT_ENUM.getValue())
        self.assertEqual(StrEnum.BAR_STRING, Config.STRING_ENUM.getValue())

    def test_getValue_invalidStore(self):
        """Tests ``ConfigEnum.getValue`` when the stored value cannot be deserialized."""
        cmds.optionVar(stringValue=(Config.FLOAT.variable, "float"))
        cmds.optionVar(stringValueAppend=(Config.INT.variable, "int_a"))
        cmds.optionVar(stringValueAppend=(Config.INT.variable, "int_b"))
        cmds.optionVar(stringValueAppend=(Config.INT.variable, "int_c"))
        # STRING is skipped here, since str can accept pretty much any type
        cmds.optionVar(intValue=(Config.FLOAT_ARRAY.variable, 6))
        cmds.optionVar(floatValue=(Config.INT_ARRAY.variable, 3.68))
        cmds.optionVar(floatValue=(Config.STRING_ARRAY.variable, 4.92))
        # BOOL is skipped here, since bool can accept pretty much any type
        cmds.optionVar(stringValue=(Config.INT_ENUM.variable, "int_enum"))
        cmds.optionVar(intValue=(Config.STRING_ENUM.variable, 7))

        self.assertEqual(1.23, Config.FLOAT.getValue())
        self.assertEqual(123, Config.INT.getValue())
        self.assertEqual([0.5, 1, 2.5], Config.FLOAT_ARRAY.getValue())
        self.assertEqual([1, 2, 5, 10, 25, 50], Config.INT_ARRAY.getValue())
        self.assertEqual(["foo", "bar"], Config.STRING_ARRAY.getValue())
        self.assertEqual(IntEnum.ONE_INT, Config.INT_ENUM.getValue())
        self.assertEqual(StrEnum.BAR_STRING, Config.STRING_ENUM.getValue())

    def test_getValue_validStore(self):
        """Tests ``ConfigEnum.getValue`` when the stored value is valid."""
        cmds.optionVar(floatValue=(Config.FLOAT.variable, 3.21))
        cmds.optionVar(intValue=(Config.INT.variable, 456))
        cmds.optionVar(stringValue=(Config.STRING.variable, "fizzbuzz"))
        cmds.optionVar(floatValueAppend=(Config.FLOAT_ARRAY.variable, 9.6))
        cmds.optionVar(floatValueAppend=(Config.FLOAT_ARRAY.variable, 7.4))
        cmds.optionVar(intValueAppend=(Config.INT_ARRAY.variable, -1))
        cmds.optionVar(intValueAppend=(Config.INT_ARRAY.variable, -2))
        cmds.optionVar(intValueAppend=(Config.INT_ARRAY.variable, -3))
        cmds.optionVar(stringValueAppend=(Config.STRING_ARRAY.variable, "fizz"))
        cmds.optionVar(stringValueAppend=(Config.STRING_ARRAY.variable, "buzz"))
        cmds.optionVar(stringValueAppend=(Config.STRING_ARRAY.variable, "sparkle"))
        cmds.optionVar(intValue=(Config.BOOL.variable, 0))
        cmds.optionVar(intValue=(Config.INT_ENUM.variable, 3))
        cmds.optionVar(stringValue=(Config.STRING_ENUM.variable, "baz"))

        self.assertEqual(3.21, Config.FLOAT.getValue())
        self.assertEqual(456, Config.INT.getValue())
        self.assertEqual("fizzbuzz", Config.STRING.getValue())
        self.assertEqual([9.6, 7.4], Config.FLOAT_ARRAY.getValue())
        self.assertEqual([-1, -2, -3], Config.INT_ARRAY.getValue())
        self.assertEqual(["fizz", "buzz", "sparkle"], Config.STRING_ARRAY.getValue())
        self.assertIs(False, Config.BOOL.getValue())
        self.assertIs(IntEnum.THREE_INT, Config.INT_ENUM.getValue())
        self.assertIs(StrEnum.BAZ_STRING, Config.STRING_ENUM.getValue())

    def test_setValue(self):
        """Tests ``ConfigEnum.setValue``."""
        Config.FLOAT.setValue(3.45)
        Config.INT.setValue(789)
        Config.STRING.setValue("my_string")
        Config.FLOAT_ARRAY.setValue([1.2, 2.5])
        Config.INT_ARRAY.setValue([-1, 0])
        Config.STRING_ARRAY.setValue(["alpha", "bravo", "charlie", "delta"])
        Config.BOOL.setValue(False)
        Config.INT_ENUM.setValue(IntEnum.TWO_INT)
        Config.STRING_ENUM.setValue(StrEnum.FOO_STRING)

        self.assertEqual(3.45, cmds.optionVar(query=Config.FLOAT.variable))
        self.assertEqual(789, cmds.optionVar(query=Config.INT.variable))
        self.assertEqual("my_string", cmds.optionVar(query=Config.STRING.variable))
        self.assertEqual([1.2, 2.5], cmds.optionVar(query=Config.FLOAT_ARRAY.variable))
        self.assertEqual([-1, 0], cmds.optionVar(query=Config.INT_ARRAY.variable))
        self.assertEqual(
            ["alpha", "bravo", "charlie", "delta"],
            cmds.optionVar(query=Config.STRING_ARRAY.variable),
        )
        self.assertEqual(0, cmds.optionVar(query=Config.BOOL.variable))
        self.assertEqual(2, cmds.optionVar(query=Config.INT_ENUM.variable))
        self.assertEqual("foo", cmds.optionVar(query=Config.STRING_ENUM.variable))


if __name__ == "__main__":
    from maya_test import main

    main()
