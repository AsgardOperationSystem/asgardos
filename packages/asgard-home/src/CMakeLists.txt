cmake_minimum_required(VERSION 3.21)
project(asgard-home LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 REQUIRED COMPONENTS Gui Network Qml Quick)

# rcheevos ROM hashing only (see 3rdparty/rcheevos/VERSION)
file(GLOB RHASH 3rdparty/rcheevos/src/rhash/*.c)
add_library(rhash STATIC ${RHASH} 3rdparty/rcheevos/src/rc_compat.c)
target_include_directories(rhash PUBLIC 3rdparty/rcheevos/include PRIVATE 3rdparty/rcheevos/src)

add_executable(asgard-home main.cpp backend.cpp achievements.cpp music.cpp files.cpp osk.cpp panel.cpp)
target_link_libraries(asgard-home PRIVATE Qt6::Gui Qt6::Network Qt6::Qml Qt6::Quick rhash)
find_package(LayerShellQt QUIET)   # the OSD overlay; without it (desktop dev builds) a plain window
if(LayerShellQt_FOUND)
  target_link_libraries(asgard-home PRIVATE LayerShellQt::Interface)
  target_compile_definitions(asgard-home PRIVATE HAVE_LAYERSHELL)
endif()
install(TARGETS asgard-home DESTINATION bin)
# Asgard Music: the same binary as asgard-home --music; its own name, so quitting it never kills Home (killall).
install(CODE "file(CREATE_LINK asgard-home \$ENV{DESTDIR}\${CMAKE_INSTALL_PREFIX}/bin/asgard-music SYMBOLIC)")
install(PROGRAMS start_asgard-music.sh DESTINATION bin)
# Asgard Files (Tools > Files): asgard-home --files, under its own name too.
install(CODE "file(CREATE_LINK asgard-home \$ENV{DESTDIR}\${CMAKE_INSTALL_PREFIX}/bin/asgard-files SYMBOLIC)")
install(PROGRAMS start_asgard-files.sh DESTINATION bin)
# Asgard Keyboard (Tools' touch keyboard): asgard-home --osk <app_id>, under its own name (Home's Quit kills by name).
install(CODE "file(CREATE_LINK asgard-home \$ENV{DESTDIR}\${CMAKE_INSTALL_PREFIX}/bin/asgard-osk SYMBOLIC)")
# Thor Panel (the AYN button, thor_ayn_button.py): asgard-home --panel, under its own name too.
install(CODE "file(CREATE_LINK asgard-home \$ENV{DESTDIR}\${CMAKE_INSTALL_PREFIX}/bin/asgard-panel SYMBOLIC)")
# A game's text prompt (thor_text_input.py): asgard-home --text-input, under its own name too.
install(CODE "file(CREATE_LINK asgard-home \$ENV{DESTDIR}\${CMAKE_INSTALL_PREFIX}/bin/asgard-text-input SYMBOLIC)")
install(DIRECTORY qml/ DESTINATION share/asgard-home/qml)
# Built-in art and gamelist entries (media/<system>/, ES-DE layout) for entries Asgard ships, like Tools > Firefox.
install(DIRECTORY media/ DESTINATION share/asgard-home/media PATTERN "*.py" EXCLUDE)   # not make_tools_art.py
