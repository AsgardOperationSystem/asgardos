# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS

PKG_NAME="eden-duo-sa"
PKG_VERSION="5fa93ed4de1a3f0838f01ef999eaa4a6582055ef" # Eden Duo 1.3.2.2
PKG_LICENSE="GPL-3.0-or-later"
PKG_SITE="https://github.com/igawa6/eden-duo"
PKG_URL="${PKG_SITE}.git"
PKG_DEPENDS_TARGET="toolchain glslang:host ffmpeg SDL3 boost zlib libusb zstd lz4 openssl opus libfmt nlohmann-json \
                    spirv-tools spirv-headers vulkan-headers enet libzip ${VULKAN}"
PKG_LONGDESC="Eden Duo - Eden (Switch) fork with live dual-screen game companions (.dsmod); its SDL3 eden-cli frontend,
whose second window (\"Eden - Screen 2 (DSMod aux)\") shows the companion with touch"

# Like eden-sa, but only the SDL3 frontend (eden-cli): Eden Duo's desktop companion window lives there, not in Qt.
# ENABLE_WERROR off: with GCC the companion code (src/core/mods) trips -Werror=shadow/unused (upstream builds Android
# with Clang); they stay warnings.
PKG_CMAKE_OPTS_TARGET="-DCMAKE_BUILD_TYPE=Release \
                       -DENABLE_WERROR=OFF \
                       -DVulkanHeaders_FORCE_BUNDLED=ON \
                       -DENABLE_QT=OFF \
                       -DYUZU_CMD=ON \
                       -DYUZU_USE_BUNDLED_SDL3=OFF \
                       -DYUZU_USE_BUNDLED_FFMPEG=OFF \
                       -DENABLE_UPDATE_CHECKER=OFF \
                       -DENABLE_WEB_SERVICE=OFF \
                       -DUSE_DISCORD_PRESENCE=OFF \
                       -DYUZU_ROOM=OFF \
                       -DYUZU_ROOM_STANDALONE=OFF \
                       -DYUZU_TESTS=OFF \
                       -DYUZU_DISABLE_LLVM=ON"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/bin
    cp -a ${PKG_BUILD}/.${TARGET_NAME}/bin/eden-cli ${INSTALL}/usr/bin/eden-duo-cli
    cp -a ${PKG_DIR}/scripts/start_eden-duo.sh ${INSTALL}/usr/bin
}
