cmake_minimum_required(VERSION 3.21)
project(asgard-home LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 REQUIRED COMPONENTS Gui Network Qml Quick)

# rcheevos ROM hashing only (see 3rdparty/rcheevos/VERSION)
file(GLOB RHASH 3rdparty/rcheevos/src/rhash/*.c)
add_library(rhash STATIC ${RHASH} 3rdparty/rcheevos/src/rc_compat.c)
target_include_directories(rhash PUBLIC 3rdparty/rcheevos/include PRIVATE 3rdparty/rcheevos/src)

add_executable(asgard-home main.cpp backend.cpp achievements.cpp music.cpp)
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
install(DIRECTORY qml/ DESTINATION share/asgard-home/qml)
