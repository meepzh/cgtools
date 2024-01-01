try:
    from maya_packaging import get_python_version
except ImportError:
    # https://github.com/meepzh/rez-recipes was not installed and directed to by
    # package_definition_build_python_paths. As such, we disable Python compilation,
    # since it's unclear what specific Python version is being used within DCCs.
    __python_version = None
else:
    __python_version = get_python_version()


name = "cgtools"


authors = ["Robert Zhou"]


def commands():
    env.PYTHONPATH.append("{root}/python")


description = "Personal repository for small CG-related Python tools"


hashed_variants = True


def pre_build_commands():
    # Imports are not transferred to the pre_build, so rerun the test
    try:
        import maya_packaging
    except ImportError:
        env.REZ_BUILD_INSTALL_PYC = 0


requires = [
    "PySide2-5.12+<6",
    "python-3.5+",
]


uuid = "33f93d29427d4d72ade889c2fd5f7ef6"


@early()
def variants():
    if __python_version:
        variants = [
            ["!maya", "python-*.*"],
            ["maya", f"python-{this.__python_version.rpartition('.')[0]}"],
        ]
    else:
        variants = [
            ["!maya"],
            ["maya"],
        ]
    return variants


version = "1.0.0"
