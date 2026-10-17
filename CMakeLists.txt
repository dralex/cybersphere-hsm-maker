cmake_minimum_required(VERSION 3.16)

# the Debian package of the maker and its editor plugin; nothing is compiled
project(cybersphere-hsm-maker VERSION 0.1.0 LANGUAGES NONE)

# the place of the pure Python packages on Debian
set(PYTHON_INSTALL_DIR "lib/python3/dist-packages" CACHE STRING
    "the directory of the hsm_maker package under the prefix")
# the system plugin folder of CyberiadaPro
set(PLUGIN_INSTALL_DIR "share/cyberiada-pro/plugins/hsm-maker")
set(DOC_INSTALL_DIR "share/doc/python3-cybersphere-hsm-maker")
# the package directories do not follow the umask of the build
set(CMAKE_INSTALL_DEFAULT_DIRECTORY_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
    GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE)

install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/hsm_maker
        DESTINATION ${PYTHON_INSTALL_DIR}
        FILES_MATCHING PATTERN "*.py" PATTERN "*.md" PATTERN "*.json"
        PATTERN "__pycache__" EXCLUDE)

# the command, as the wheel's entry point makes it
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/hsm-maker
     "#!/usr/bin/python3\nimport sys\nfrom hsm_maker.cli import main\nsys.exit(main())\n")
install(PROGRAMS ${CMAKE_CURRENT_BINARY_DIR}/hsm-maker DESTINATION bin)

install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/editor-plugin/plugin.json
              ${CMAKE_CURRENT_SOURCE_DIR}/editor-plugin/README.md
        DESTINATION ${PLUGIN_INSTALL_DIR})
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/editor-plugin/icons
                  ${CMAKE_CURRENT_SOURCE_DIR}/editor-plugin/i18n
        DESTINATION ${PLUGIN_INSTALL_DIR})

install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/ChangeLog.md
              ${CMAKE_CURRENT_SOURCE_DIR}/README.md
              ${CMAKE_CURRENT_SOURCE_DIR}/LICENSE
        DESTINATION ${DOC_INSTALL_DIR})

# the machine-readable (DEP-5) copyright, where the Debian policy wants it
install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/debian-copyright
        DESTINATION ${DOC_INSTALL_DIR} RENAME copyright)

# the tests need pytest and the CyberiadaML binding in this Python
# (-DPython3_EXECUTABLE=... selects a virtual environment)
find_package(Python3 3.8 COMPONENTS Interpreter)
if(Python3_FOUND)
  enable_testing()
  add_test(NAME pytest
           COMMAND ${Python3_EXECUTABLE} -B -m pytest -q -p no:cacheprovider tests
           WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
endif()

# optional per-release suffix (e.g. ubuntu2404) for the package version: the
# package is tested against that release's libraries and Python
set(DISTRO_TAG "" CACHE STRING "distribution suffix appended to the package version")
configure_file("${PROJECT_SOURCE_DIR}/HsmMakerPackOptions.cmake.in"
               "${PROJECT_BINARY_DIR}/HsmMakerPackOptions.cmake"
               @ONLY)
set(CPACK_PROJECT_CONFIG_FILE "${PROJECT_BINARY_DIR}/HsmMakerPackOptions.cmake")

include(CPack)
