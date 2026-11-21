# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS (https://github.com/AsgardOperationSystem)

PKG_NAME="gba-ds-sa"
PKG_VERSION="3b452dc9005e2a71e02c423be21790dfcfc0ca0c" # v1.5.6
PKG_SHA256="0ea49bd7dd541889ae45a00de9bf7f25d3b233ee3058ab8a858441aaf0d83a95"
PKG_LICENSE="GPL-3.0-only"
PKG_SITE="https://github.com/kyannon/gba-ds"
PKG_URL="${PKG_SITE}/archive/refs/tags/v1.5.6.tar.gz"
PKG_SOURCE_DIR="gba-ds-1.5.6"
PKG_DEPENDS_TARGET="toolchain SDL2 gba-ds-mgba"
PKG_DEPENDS_UNPACK="gba-ds-mgba"
PKG_LONGDESC="Dual-screen Game Boy Advance: mGBA on the top screen, the game's map or HUD on the bottom one."
PKG_TOOLCHAIN="manual"

# libmgba as GBA DS's scripts/mgba-options.sh builds it: static, no frontends, mGBA's own zlib and LZMA
# (the policy minimum: the build container's CMake 4 refuses mGBA's bundled zlib, which asks for CMake < 3.5)
MGBA_OPTS="-DLIBMGBA_ONLY=OFF -DBUILD_STATIC=ON -DBUILD_SHARED=OFF -DCMAKE_BUILD_TYPE=Release -DBUILD_LTO=OFF \
  -DBUILD_SDL=OFF -DBUILD_QT=OFF -DBUILD_LIBRETRO=OFF -DBUILD_GL=OFF -DBUILD_GLES2=OFF -DBUILD_GLES3=OFF \
  -DBUILD_PERF=OFF -DBUILD_TEST=OFF -DBUILD_SUITE=OFF -DBUILD_CINEMA=OFF -DBUILD_ROM_TEST=OFF \
  -DBUILD_UPDATER=OFF -DBUILD_HEADLESS=OFF -DBUILD_PYTHON=OFF -DUSE_EPOXY=OFF \
  -DENABLE_DEBUGGERS=OFF -DENABLE_GDB_STUB=OFF -DUSE_EDITLINE=OFF -DUSE_SQLITE3=OFF -DUSE_ELF=OFF \
  -DUSE_LZMA=ON -DUSE_ZLIB=ON -DUSE_PNG=OFF -DUSE_LIBZIP=OFF -DUSE_MINIZIP=OFF -DUSE_FFMPEG=OFF \
  -DUSE_LUA=OFF -DUSE_JSON_C=OFF -DUSE_DISCORD_RPC=OFF -DUSE_FREETYPE=OFF -DM_CORE_GB=OFF \
  -DENABLE_SCRIPTING=OFF -DDISABLE_DEPS=OFF \
  -DCMAKE_DISABLE_FIND_PACKAGE_ZLIB=ON -DCMAKE_DISABLE_FIND_PACKAGE_PkgConfig=ON \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5"

make_target() {
  MGBA_SRC=$(get_build_dir gba-ds-mgba)
  MGBA_BUILD=${PKG_BUILD}/.mgba-${TARGET_NAME}
  cmake -S ${MGBA_SRC} -B ${MGBA_BUILD} -DCMAKE_TOOLCHAIN_FILE=${CMAKE_CONF} ${MGBA_OPTS}
  make -C ${MGBA_BUILD} mgba zlibstatic
  make CROSS=${TARGET_PREFIX} MGBA_SRC=${MGBA_SRC} MGBA_BUILD=${MGBA_BUILD} SDL_PREFIX=${SYSROOT_PREFIX}/usr \
       OUT=${PKG_BUILD}/.${TARGET_NAME} OPTFLAGS="-O2"
}

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/bin
    cp -a ${PKG_BUILD}/.${TARGET_NAME}/gba-ds ${INSTALL}/usr/bin
    cp -a ${PKG_DIR}/scripts/* ${INSTALL}/usr/bin
}
