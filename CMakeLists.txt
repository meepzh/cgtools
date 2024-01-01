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
set(python_destination "python/${REZ_BUILD_PROJECT_NAME}")

# Prepare and install Python files
file(GLOB_RECURSE py_files "python/*.py")
if(NOT MAYA)
  list(FILTER py_files EXCLUDE REGEX ${maya_regex})
endif()
# rez_install_python hardcodes the executable name, so use install_python
# directly
install_python(
  py
  FILES
  ${py_files}
  RELATIVE
  "python"
  BIN
  ${PYTHON_EXE}
  DESTINATION
  ${python_destination})

# Prepare and install other Python-related files
file(GLOB_RECURSE non_py_files "python/*")
list(FILTER non_py_files EXCLUDE REGEX "\\.py$")
if(NOT MAYA)
  list(FILTER non_py_files EXCLUDE REGEX ${maya_regex})
endif()
if(non_py_files)
  rez_install_files(${non_py_files} RELATIVE "python" DESTINATION
                    ${python_destination})
endif()
