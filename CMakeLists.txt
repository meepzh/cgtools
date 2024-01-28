cmake_minimum_required(VERSION 2.8)

include(RezBuild)

# Prepare configuration
if(DEFINED ENV{REZ_MAYA_VERSION})
  set(MAYA ON)
else()
  set(MAYA OFF)
endif()

if(DEFINED ENV{PYTHON_EXE})
  set(PYTHON_EXE $ENV{PYTHON_EXE})
else()
  set(PYTHON_EXE "python")
endif()

# Common variables
set(maya_regex "/maya/")

# Prepare and install Python files
file(GLOB_RECURSE py_files "python/${REZ_BUILD_PROJECT_NAME}/*.py")
if(NOT MAYA)
  list(FILTER py_files EXCLUDE REGEX ${maya_regex})
endif()
# rez_install_python hardcodes the executable name, so use install_python
# directly
install_python(
  py
  FILES
  ${py_files}
  BIN
  ${PYTHON_EXE}
  DESTINATION
  .)

# Prepare and install other Python-related files
file(GLOB_RECURSE non_py_files "python/${REZ_BUILD_PROJECT_NAME}/*")
list(FILTER non_py_files EXCLUDE REGEX "\\.py$")
if(NOT MAYA)
  list(FILTER non_py_files EXCLUDE REGEX ${maya_regex})
endif()
if(non_py_files)
  rez_install_files(${non_py_files} DESTINATION .)
endif()

# Install configuration files
rez_install_dirs("config" DESTINATION .)

# Install Maya shelves, if applicable
if(MAYA)
  rez_install_dirs("shelves" DESTINATION .)
endif()
