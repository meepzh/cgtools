"""Allows the user to flood select contiguous sections of polygonal geometry, similar to
Cinema 4D's "Fill Selection" tool.

Example::

    from cgtools.maya.ui.fill_selection import fillSelection
    fillSelection()
"""
from collections.abc import (
    Collection,
    Iterable,
    Mapping,
    MutableMapping,
    MutableSequence,
)
import dataclasses
import enum
import logging
from typing import (
    Any,
    cast,
)

from maya import cmds
import maya.api.OpenMaya as om

from cgtools.maya.config_enum import (
    ConfigEnum,
    ConfigVar,
)
from cgtools.maya.undo import undoChunk


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _SessionData:
    """Stores information about the active session (i.e.: data held while the software
    is awaiting user input before finalizing).
    """

    # Stores Maya API callback IDs
    callbackIDs: Collection[int] = dataclasses.field(default_factory=list)

    # Stores the edge mapping used to cut the given shapes
    shapeToEdges: Mapping[str, Collection[str]] = dataclasses.field(
        default_factory=dict
    )

    # Stores index-mapped collections of non-DAG-object nodes prior to this tool
    history: Collection[Collection[str]] = dataclasses.field(default_factory=list)

    # Stores scriptJob job numbers
    jobNumbers: Collection[int] = dataclasses.field(default_factory=list)

    # Stores the index-mapped names of the UV sets that were marked "current"
    previousUVSets: Collection[str] = dataclasses.field(default_factory=list)

    # Provides index mapping to the shapes affected by this session
    shapes: Collection[str] = dataclasses.field(default_factory=list)

    # Stores any selection information to be preserved in the session
    selection: Collection[str] = dataclasses.field(default_factory=list)

    def __bool__(self) -> bool:
        """Returns whether a session is active or not.

        Returns:
            True if a session is active.
        """
        return any(getattr(self, field.name) for field in dataclasses.fields(self))

    def clear(self) -> None:
        """Clears the stored session data, particularly removing callbacks and
        scriptJobs.
        """
        logger.debug("Clearing session data")

        for callbackID in self.callbackIDs:
            om.MMessage.removeCallback(callbackID)

        for jobNumber in self.jobNumbers:
            cmds.scriptJob(kill=jobNumber)

        for field in dataclasses.fields(self):
            getattr(self, field.name).clear()


# Avoid losing the session data during module reloads
try:
    # pylint: disable-next=used-before-assignment
    _sessionData is not None  # type: ignore[has-type,used-before-def]
except NameError:
    # Stores information about the active session (i.e.: data held while the software
    # is awaiting user input before finalizing).
    _sessionData = _SessionData()


class _StrEnum(str, enum.Enum):
    """Backport of Python 3.11's ``StrEnum`` class."""

    def __str__(self) -> str:
        """Allows simple conversion of the enum to its value.

        Returns:
            The enum value.
        """
        return self.value

    @staticmethod
    def _generate_next_value_(
        name: str, _start: int, _count: int, _last_values: list[Any]
    ) -> str:
        """Sets ``auto()`` values to the lower-case of each member's name.

        Args:
            name: The member name
        """
        return name.lower()


class ComponentType(_StrEnum):
    """Polygon component types that can be produced."""

    EDGE = enum.auto()
    FACE = enum.auto()
    VERTEX = enum.auto()


class EdgesFrom(_StrEnum):
    """Determines how non-edge selections will be converted to edges."""

    # Faces: All edges connected to any selected face will be used
    # Vertices: All edges connected to any selected vertex will be used
    # Vertex Faces: All edges connected to any selected vertex face will be used
    ALL = enum.auto()

    # Faces: Only edges that share both sides with a selected face will be used
    # Vertices: Only edges that share both end points with a selected vertex will be
    #     used
    # Vertex Faces: Only edges with all four vertex faces selected
    CONTAINED = enum.auto()

    # Faces: Only edges that share one side with a selected face will be used
    # Vertices: Only edges that share one face with a selected vertex will be used
    # Vertex Faces: Only edges that border faces with a selected vertex face will be
    #     used
    PERIMETER = enum.auto()


class ExitOn(_StrEnum):
    """Determines when the temporary fill selection will be converted."""

    # Exits when the enter key is pressed inside a viewport
    ENTER_KEY = enum.auto()

    # Exits when the code is called again
    REINVOCATION = enum.auto()

    # Exits immediately after a selection is made
    SELECTION = enum.auto()


class Config(ConfigEnum):
    """OptionVars with additional convenience functionality."""

    # How face selections will be used to determine fill boundaries
    CONVERT_FACES_TO = ConfigVar(default=EdgesFrom.PERIMETER, serialize=str)

    # How vertex selections will be used to determine fill boundaries
    CONVERT_VERTICES_TO = ConfigVar(default=EdgesFrom.CONTAINED, serialize=str)

    # How vertex face selections will be used to determine fill boundaries
    CONVERT_VERTEX_FACES_TO = ConfigVar(default=EdgesFrom.ALL, serialize=str)

    # Primary determination for when the temporary fill selection is converted to
    # typical polygon components and the supporting nodes are cleaned
    EXIT_CONDITION = ConfigVar(default=ExitOn.SELECTION, serialize=str)

    # The user may not be aware that this tool takes advantage of the UV shell
    # selection, so the tool will typically exit once they leave that selection mode or
    # type, perhaps to fine tune parts of the selection.
    EXIT_ON_SELECT_MODETYPE_CHANGE = ConfigVar(default=True, serialize=int)

    # Determines the type of polygon components to convert to
    OUTPUT_TYPE = ConfigVar(default=ComponentType.FACE, serialize=str)

    # If True, existing UV seams on the objects' current UV set will also delineate fill
    # boundaries
    USE_EXISTING_SEAMS = ConfigVar(default=False, serialize=int)


def fillSelection() -> None:
    """Interactively separates the selected meshes into contiguous sections, separated
    by any component selections that the user has made. This allows the user to select
    one of those sections easily.

    Running this method on a clean scene generates session data that can be used to
    reapply the changes if it needs to be removed temporarily, e.g. when saving scenes.
    """
    if _sessionData and Config.EXIT_CONDITION.getValue() == ExitOn.REINVOCATION:
        # Invoked again and exit on reinvocation was requested, so call finalize()
        finalize()
        return

    shapes: Collection[str] = _getSelectedShapes()
    if not shapes:
        cmds.warning("Please select a polygon mesh or its components.")
        return

    # The construction history should end the same as how it started
    # But there doesn't appear to be a good way of doing this without keeping track of
    # it and removing any nodes created here
    history: MutableSequence[Collection[str]] = []
    for shape in shapes:
        history.append(cmds.listHistory(shape, pruneDagObjects=True) or [])

    # Determine what edges will be used to cut each shape's UVs
    shapeToEdges = cast(MutableMapping[str, Collection[str]], _getEdgesFromSelection())

    # "Restore" the changes from the session data
    _sessionData.history = history
    _sessionData.shapeToEdges = shapeToEdges
    _restoreSession()

    # Starts callbacks for interactivity
    _startSession()


@undoChunk("Convert the fill selection")
def finalize() -> None:
    """Converts the selection and cleans up the session."""
    selection = cmds.ls(selection=True)
    logger.debug("Finalizing with selection: %s", selection)

    match Config.OUTPUT_TYPE.getValue():
        case ComponentType.EDGE:
            selection = cmds.polyListComponentConversion(selection, toEdge=True)
            _changeSelectType(type_="polymeshEdge")
        case ComponentType.FACE:
            selection = cmds.polyListComponentConversion(selection, toFace=True)
            _changeSelectType(type_="polymeshFace")
        case ComponentType.VERTEX:
            selection = cmds.polyListComponentConversion(selection, toVertex=True)
            _changeSelectType(type_="polymeshVtxFace")

    cmds.evalDeferred(_cleanUp)
    cmds.select(selection)

    # Clear the callbacks and such outside of the scriptJob
    cmds.evalDeferred(_sessionData.clear)


def onMayaDroppedPythonFile() -> None:
    """Installs this file as its own module, allowing usage without needing to build
    the whole cgtools package and its dependencies.
    """
    raise NotImplementedError(
        "Drag and drop functionality has not been implemented yet."
    )


def _changeSelectType(
    shapes: Iterable[str] | None = None, type_: str = "meshUVShell"
) -> None:
    """Changes to the UV shell selection type for the given shapes.

    In particular, this derives from the doMenuComponentSelection proc, which preserves
    the user's selection mode.

    Args:
        shapes: The shapes to enable selection for.
        type_: The type of selection to enable.
    """
    if cmds.selectMode(query=True, object=True):
        cmds.selectType(objectComponent=True, allComponents=False)
        cmds.selectType(objectComponent=True, **{type_: True})
    cmds.selectType(**{type_: True})

    if shapes:
        transforms = set(cmds.listRelatives(list(shapes), parent=True, path=True))
        cmds.hilite(transforms)


@undoChunk("Clean up changes from fill selection")
def _cleanUp() -> None:
    """Removes any extra nodes created on the affected shapes. This does not clear
    session data.
    """
    _sessionData.selection = cmds.ls(selection=True)
    logger.debug("Cleaning up with selection: %s", _sessionData.selection)

    # Remove new nodes
    for shape, history in zip(_sessionData.shapeToEdges.keys(), _sessionData.history):
        newNodes = set(cmds.listHistory(shape, pruneDagObjects=True)) - set(history)
        logger.debug("Cleaning up nodes for %s: %r", shape, newNodes)
        cmds.delete(newNodes)

    # Reset which UV sets are "current"
    for shape, previousUVSet in zip(
        _sessionData.shapeToEdges.keys(), _sessionData.previousUVSets
    ):
        cmds.polyUVSet(shape, currentUVSet=True, uvSet=previousUVSet)


def _getEdgesFromSelectedFaces() -> list[str]:
    """Converts the faces selected in scene to edges based on the preferred conversion
    method.

    Returns:
        The edges that were determined from the face selection.
    """
    convertFacesTo = Config.CONVERT_FACES_TO.getValue()
    selection = cmds.filterExpand(expand=False, selectionMask=34) or []
    match convertFacesTo:
        case EdgesFrom.ALL:
            selection = cmds.polyListComponentConversion(
                selection,
                fromFace=True,
                toEdge=True,
            )
        case EdgesFrom.CONTAINED:
            selection = cmds.polyListComponentConversion(
                selection,
                fromFace=True,
                toEdge=True,
                internal=True,
            )
        case EdgesFrom.PERIMETER:
            selection = cmds.polyListComponentConversion(
                selection,
                fromFace=True,
                toEdge=True,
                border=True,
            )
    return selection


def _getEdgesFromSelectedVertices() -> list[str]:
    """Converts the vertices selected in scene to edges based on the preferred
    conversion method.

    Returns:
        The edges that were determined from the vertex selection.
    """
    convertVerticesTo = Config.CONVERT_VERTICES_TO.getValue()
    selection = cmds.filterExpand(expand=False, selectionMask=31) or []
    match convertVerticesTo:
        case EdgesFrom.ALL:
            selection = cmds.polyListComponentConversion(
                selection,
                fromVertex=True,
                toEdge=True,
            )
        case EdgesFrom.CONTAINED:
            selection = cmds.polyListComponentConversion(
                selection,
                fromVertex=True,
                toEdge=True,
                internal=True,
            )
        case EdgesFrom.PERIMETER:
            selection = cmds.polyListComponentConversion(
                selection,
                fromVertex=True,
                toFace=True,
            )
            selection = cmds.polyListComponentConversion(
                selection,
                fromFace=True,
                toEdge=True,
                border=True,
            )
    return selection


def _getEdgesFromSelectedVertexFaces() -> list[str]:
    """Converts the vertex faces selected in scene to edges based on the preferred
    conversion method.

    Returns:
        The edges that were determined from the vertex face selection.
    """
    convertVertexFacesTo = Config.CONVERT_VERTEX_FACES_TO.getValue()
    selection = cmds.filterExpand(expand=False, selectionMask=70) or []
    match convertVertexFacesTo:
        case EdgesFrom.ALL:
            selection = cmds.polyListComponentConversion(
                selection,
                fromVertexFace=True,
                toEdge=True,
                vertexFaceAllEdges=True,
            )
        case EdgesFrom.CONTAINED:
            selection = cmds.polyListComponentConversion(
                selection,
                fromVertexFace=True,
                toEdge=True,
                internal=True,
            )
        case EdgesFrom.PERIMETER:
            selection = cmds.polyListComponentConversion(
                selection,
                fromVertexFace=True,
                toFace=True,
            )
            selection = cmds.polyListComponentConversion(
                selection, fromFace=True, toEdge=True, border=True
            )
    return selection


def _getEdgesFromSelection() -> dict[str, list[str]]:
    """Convert selection to edges.

    Returns:
        A mapping of shapes to their converted edge selection.
    """
    edges: list[str] = cmds.filterExpand(expand=False, selectionMask=32) or []
    edges.extend(_getEdgesFromSelectedFaces())
    edges.extend(_getEdgesFromSelectedVertices())
    edges.extend(_getEdgesFromSelectedVertexFaces())
    return _partitionEdgesByShape(edges)


def _getMeshShapes(transform: str) -> list[str]:
    """Returns any mesh shapes found under the given transform.

    Args:
        transform: The name of the transform object.

    Returns:
        A list of shape paths.
    """
    return (
        cmds.listRelatives(
            transform, shapes=True, noIntermediate=True, path=True, type="mesh"
        )
        or []
    )


def _getSelectedShapes() -> set[str]:
    """Get the current selection as objects.

    While many cmds will work with component selections, it gets confusing when there
    is a component selection on object A, a selection on object B, and then another
    component selection on object A, as sometimes operations will return two objects
    and sometimes three.

    Returns:
        The shapes.
    """
    objects: set[str] = set(cmds.ls(selection=True, objectsOnly=True))

    # Filter for mesh shapes
    shapes: set[str] = set()
    for object_ in objects:
        if cmds.objectType(object_, isAType="mesh"):
            shapes.add(object_)
        if cmds.objectType(object_, isAType="transform"):
            shapes.update(_getMeshShapes(object_))

    return shapes


def _partitionEdgesByShape(edges: Iterable[str]) -> dict[str, list[str]]:
    """Partitions the collection of edges by the shapes they belong to.

    Args:
        edges: The edges to partition.

    Returns:
        A mapping of shapes to their selected edges.
    """
    mapping: dict[str, list[str]] = {}

    for edgeRange in edges:
        object_, _, range_ = edgeRange.rpartition(".")

        if cmds.objectType(object_, isAType="transform"):
            # filterExpand may return transforms if it only has a single shape, but
            # ls may return the shape instead for component selections, so force
            # everything to shapes
            object_ = _getMeshShapes(object_)[0]

        mapping.setdefault(object_, []).append(object_ + "." + range_)

    return mapping


def _prepareUVSets(shapes: Collection[str]) -> tuple[list[str], list[str]]:
    """Sets up a new UV set that can be used for the shell selection.

    Args:
        shapes: The meshes that should be affected.

    Returns:
        The names of the meshes' original UV sets marked "current".
        The names of the new UV sets, now marked "current".
    """
    # Store the current UV set(s), as which sets are "current" will be changed
    previousUVSets: list[str] = cmds.polyUVSet(
        list(shapes), query=True, currentUVSet=True
    )

    # Create new "current" UV sets
    workingUVSets: list[str] = cmds.polyUVSet(
        list(shapes), create=True, uvSet="fillSelectionMap"
    )
    for shape, workingUVSet in zip(shapes, workingUVSets):
        cmds.polyUVSet(shape, edit=True, uvSet=workingUVSet, currentUVSet=True)
        if Config.USE_EXISTING_SEAMS.getValue():
            # Copy the previous current UV set to the new current
            cmds.polyUVSet(shape, copy=True, newUVSet=workingUVSet)
        else:
            # Apply planar projections as they are simple and have no seams
            cmds.polyPlanarProjection(shape)

    return (previousUVSets, workingUVSets)


@undoChunk("Prepare the scene for fill selection")
def _restoreSession() -> None:
    """Reapplies the session data to a clean scene."""
    logger.debug("Restoring session")

    # Set up new UV sets to apply cuts to
    _sessionData.previousUVSets, _ = _prepareUVSets(_sessionData.shapeToEdges)

    # Apply the cuts one shape at a time due to limitations with polyMapCut
    for edges in _sessionData.shapeToEdges.values():
        cmds.polyMapCut(edges)

    # Set the selection type to UV shells
    _changeSelectType(shapes=_sessionData.shapeToEdges)

    # Restore selection, if any
    if _sessionData.selection:
        cmds.select(_sessionData.selection)


def _startSession() -> None:
    """"""
    callbackIDs: list[int] = []
    jobNumbers: list[int] = []

    # Set up exit conditions
    match Config.EXIT_CONDITION.getValue():
        case ExitOn.ENTER_KEY:
            # The idea would be to find all viewport widgets and add an event filter to
            # them, calling finalize() when the enter key is detected.
            raise NotImplementedError(
                "Support for finalizing the fill selection using the enter key has not "
                "been added yet."
            )

        case ExitOn.SELECTION:

            def finalizeAfterSelectionChanged() -> None:
                """Finalizes the fill selection process after a selection change."""
                logger.debug("Finalize due to selection change")
                finalize()

            jobNumbers.append(
                cmds.scriptJob(
                    event=("SelectionChanged", finalizeAfterSelectionChanged)
                )
            )

    # Account for changes away from the current selection mode or type
    if Config.EXIT_ON_SELECT_MODETYPE_CHANGE.getValue():

        def finalizeAfterSelectModeChanged() -> None:
            """Finalizes the fill selection process after a select mode change."""
            logger.debug("Finalize due to select mode change")
            finalize()

        jobNumbers.append(
            cmds.scriptJob(event=("SelectModeChanged", finalizeAfterSelectModeChanged))
        )

        def finalizeAfterSelectTypeChanged() -> None:
            """Finalizes the fill selection process after a select type change."""
            logger.debug("Finalize due to select type change")
            finalize()

        jobNumbers.append(
            cmds.scriptJob(event=("SelectTypeChanged", finalizeAfterSelectTypeChanged))
        )

    # Tool changes can affect construction history, so be sure to exit there
    def finalizeAfterToolChanged() -> None:
        """Finalizes the fill selection process after a tool change."""
        logger.debug("Finalize due to tool change")
        finalize()

    jobNumbers.append(cmds.scriptJob(event=("ToolChanged", finalizeAfterToolChanged)))

    # Account for scene changes
    def cleanUpBeforeSave(_clientData: None) -> None:
        """Cleans up the scene changes that only make sense in the tool's context.

        Args:
            _clientData: There is no client data being passed to this callback.
        """
        logger.debug("Cleaning up before save")
        _cleanUp()

    callbackIDs.append(
        om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeSave, cleanUpBeforeSave)
    )

    def restoreSessionAfterSave(_clientData: None) -> None:
        """Restores the scene changes to return to the tool's context.

        Args:
            _clientData: There is no client data being passed to this callback.
        """
        logger.debug("Restoring session after save")
        _restoreSession()

    callbackIDs.append(
        om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterSave, restoreSessionAfterSave
        )
    )

    def clearSessionAfterNewScene(_clientData: None) -> None:
        """Removes the session due to the new scene.

        Args:
            _clientData: There is no client data being passed to this callback.
        """
        logger.debug("Clearing session after new scene")
        _sessionData.clear()

    callbackIDs.append(
        om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterNew, clearSessionAfterNewScene
        )
    )

    # Store data for finalizing the selection
    _sessionData.callbackIDs = callbackIDs
    _sessionData.jobNumbers = jobNumbers
