"""Simple configuration system allowing programs to define configuration optionVars as
an enumeration.

This allows iteration over all the available options while also providing convenience
functionality for serializing and storing values.
"""
from collections.abc import (
    Callable,
    Iterable,
)
import enum
import logging
from types import DynamicClassAttribute
from typing import (
    Any,
    Generic,
    NamedTuple,
    TypeVar,
    cast,
)

from maya import cmds


Serializable = float | int | str | Iterable[float | int | str]
T = TypeVar("T")


logger = logging.getLogger(__name__)


class _ConfigEnumImpl(Generic[T]):
    """Internal implementation of ``ConfigEnum`` because ``Generic`` types are not
    supported by the ``Enum`` metaclass. Please see ``ConfigEnum`` for documentation.
    """

    def __init__(
        self,
        default: T,
        serialize: Callable[[T], Serializable] | None = None,
        deserialize: Callable[[Serializable], T] | None = None,
    ) -> None:
        super().__init__()
        self._default = default
        logger.debug("Set '%s' default to: %r", self.name, self._default)

        if not serialize:
            # pylint: disable-next=unnecessary-lambda-assignment
            serialize = lambda value: cast(Serializable, value)
        self._serialize = serialize

        if not deserialize:
            deserialize = cast(Callable[[Serializable], T], type(default))
            logger.debug("Set '%s' deserializer to: %r", self.name, deserialize)
        self._deserialize = deserialize

        self._computeVariable()
        self._computeKeyword()

    @DynamicClassAttribute
    def name(self) -> str:
        """The name of the enum member as provided by ``Enum``.

        Returns:
            The name.
        """
        return getattr(super(), "name")

    @DynamicClassAttribute
    def value(self) -> "ConfigEnum":
        """This does not change any behavior except to add a warning when accessing this
        attribute.

        Since the option attributes can be accessed directly without needing to use the
        ``value`` attribute that this attribute overrides, and since the concept of a
        "value" is confusing when this class can retrieve a different kind of "value"
        from Maya, it seems best to at least provide a warning to discourage use here.

        Returns:
            The enum member.
        """
        logger.warning(
            "It is not recommended to access a ConfigEnum's 'value' attribute."
        )
        return cast("ConfigEnum", super())

    @DynamicClassAttribute
    def variable(self) -> str:
        """Returns the name of the optionVar that this configuration should be stored
        in.

        Returns:
            The variable name.
        """
        return self._variable

    def getValue(self) -> T:
        """Returns the value of the given option variable.

        If the variable cannot be found or if the value does not conform to the default
        value's class, then a warning is printed and the default value is returned.

        Returns:
            The stored value, if valid. Otherwise, the default value is returned.
        """
        if not cmds.optionVar(exists=self.variable):
            logger.debug("Could not find optionVar '%s'", self.variable)
            return self._default

        value = cmds.optionVar(query=self.variable)
        logger.debug("Retrieved optionVar '%s' value: %r", self.variable, value)

        try:
            value = self._deserialize(value)
        except Exception as e:  # pylint: disable=broad-exception-caught
            serializedDefault = self._serialize(self._default)

            # If the default is an enum, also provide the available options
            options = ""
            if isinstance(self._default, enum.Enum):
                options = ", ".join(
                    repr(self._serialize(cast(T, option)))
                    for option in type(self._default)
                )
                options = f"Please use: {options}. "

            cmds.warning(
                f"Failed to process the optionVar '{self.variable}'. "
                f"The following is not a valid value: {repr(value)}. "
                f"{options}"
                f"The value will be changed to: {serializedDefault}. "
                f"The error is as follows: {e}"
            )

            self.setValue(cast(T, self._default))
            value = self._default

        return value

    def setValue(self, value: T) -> None:
        """Sets the given value into the option variable in Maya.

        Args:
            value: The data to set.
        """
        serializedValue = self._serialize(value)
        logger.debug(
            "Serialized '%s' value: %r -> %r", self.name, value, serializedValue
        )
        if self._keyword.endswith("Array"):
            cmds.optionVar(clearArray=self.variable)
            writeKeyword = self._keyword[:-5] + "ValueAppend"
            for element in cast(Iterable, value):
                cmds.optionVar(**{writeKeyword: (self.variable, element)})
        else:
            cmds.optionVar(**{self._keyword: (self.variable, serializedValue)})

    def _computeKeyword(self) -> None:
        """Determines the optionVar keyword for storing the data of the default type."""
        serializedDefault = self._serialize(self._default)
        if isinstance(serializedDefault, float):
            self._keyword = "floatValue"
        elif isinstance(serializedDefault, int):
            self._keyword = "intValue"
        elif isinstance(serializedDefault, str):
            self._keyword = "stringValue"
        else:
            try:
                serializedDefault = list(serializedDefault)
            except TypeError as e:
                raise TypeError(
                    f"Expected the default for '{self.variable}' to serialize to a "
                    "single instance of or an iterable of one of the following "
                    "types: float, int, str"
                ) from e
            if isinstance(serializedDefault[0], float):
                self._keyword = "floatArray"
            elif isinstance(serializedDefault[0], int):
                self._keyword = "intArray"
            elif isinstance(serializedDefault[0], str):
                self._keyword = "stringArray"
        logger.debug("Set '%s' keyword to: %s", self.name, self._keyword)

    def _computeVariable(self) -> None:
        """Generates the variable name for the given option."""
        modulePathParts = type(self).__module__.split(".")
        modulePathParts = [part for part in modulePathParts if not part.startswith("_")]
        if len(modulePathParts) < 1:
            modulePath = type(self).__name__
        elif len(modulePathParts) == 1:
            modulePath = modulePathParts[0]
        else:
            modulePath = modulePathParts[0] + "_" + modulePathParts[-1]
        self._variable = modulePath + "_" + self.name.lower()
        logger.debug("Set '%s' variable to: %s", self.name, self._variable)


class ConfigEnum(_ConfigEnumImpl, enum.Enum):
    """Adds functionality to ``Enum`` supporting program configuration through the
    serialization and storage of Maya option variables.

    Due to the particular implementation of ``Enum``, API users are expected to subclass
    ``ConfigEnum`` and provide the various config options as members there. Values
    specific to each option would need to be passed in as a tuple, specifically
    ``ConfigVars``s.

    Example::

        from cgtools.maya.config_enum import ConfigEnum, ConfigVar

        class Config(ConfigEnum):
            FOO = ConfigVar("defaultFoo")
            BAR = ConfigVar("123", serialize=int, deserialize=str)

        Config.BAR.getValue()  # '123'

    Args:
        default: The default value of the config variable.
        serialize: The function for converting the variable value into a format that
            can be stored in Maya. By default, no conversion is done, and the value is
            passed in as is.
        deserialize: The function for converting the Maya stored value into its original
            format. By default, the type of the default value is called on the stored
            value. For example, if default is ``False``, then the type is ``bool``, so
            the following code would execute: ``value = bool(storedValue)``.

    Raises:
        TypeError: When the default value cannot be serialized to a valid optionVar
            type.
    """


class ConfigVar(NamedTuple):
    """Container of initialization variables for each configuration option, to be passed
    to ``ConfigEnum``. Please see ``ConfigEnum`` for additional documentation.

    Ideally, the type hints would look something like this::

        default: T
        serialize: Callable[[T], Serializable] | None = None
        deserialize: Callable[[Serializable], T] | None = None

    But ``Generic`` ``NamedTuple``s are not supported until Python 3.11:
    https://github.com/python/mypy/issues/685

    So for now, ``Any`` is used here.
    """

    default: Any
    serialize: Callable[[Any], Serializable] | None = None
    deserialize: Callable[[Serializable], Any] | None = None

    def __eq__(self, other: Any) -> bool:
        """The ConfigEnum may rearrange ordering if it finds two equivalent ConfigVars,
        so block that from happening by changing equivalence in values to equivalence in
        identity.

        Args:
            other: The other object.

        Returns:
            Whether the two objects are equivalent.
        """
        return self is other
