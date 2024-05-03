name = "cgtools"


authors = ["Robert Zhou"]


def commands():
    env.MAYA_SHELF_PATH.append("{root}/shelves/maya")
    env.PYTHONPATH.append("{root}/python")


description = "Personal repository for small CG-related Python tools"


hashed_variants = True


def pre_build_commands():
    # Imports are not transferred to the pre_build, so rerun the test
    try:
        import maya_packaging
    except ModuleNotFoundError:
        env.REZ_BUILD_INSTALL_PYC = 0


requires = [
    "python-3.10+",
    "rez-2+",
]


tests = {
    "unit_python": {
        "command": (
            "${PYTHON_EXE} -m unittest discover --catch "
            "--start-directory {root}/tests/python/agnostic"
        ),
        "on_variants": True,
    },
    "unit_python_maya": {
        "command": (
            "${PYTHON_EXE} {root}/tests/python/maya/maya_test.py discover --catch "
            "--start-directory {root}/tests/python/maya"
        ),
        "on_variants": {"type": "requires", "value": ["maya"]},
    },
}


uuid = "33f93d29427d4d72ade889c2fd5f7ef6"


variants = [
    ["!maya", "PySide2-5.12+<6", "python-*.*"],
    ["!maya", "PySide-6", "python-*.*"],
    ["maya-2024", "PySide2-5.12+<6", "python-3.10"],
    ["maya-2025", "PySide-6", "python-3.11"],
]


version = "1.0.0"
