# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS

PKG_NAME="eden-sa"
PKG_VERSION="58c1e20ee58efa3900ba616207d460886214480b" # tag v0.2.1
PKG_LICENSE="GPL-3.0-or-later"
PKG_SITE="https://git.eden-emu.dev/eden-emu/eden"
PKG_URL="${PKG_SITE}.git"
PKG_DEPENDS_TARGET="toolchain glslang:host ffmpeg SDL2 boost zlib libusb zstd lz4 openssl opus libfmt nlohmann-json \
                    spirv-tools spirv-headers vulkan-headers enet libzip qt6 ${VULKAN}"
PKG_LONGDESC="Eden - Nintendo Switch emulator (yuzu fork); NCE runs game code natively on arm64"

# Dependencies missing from (or too old in) the sysroot are fetched by Eden's CPMUtil at configure time.
# Vulkan headers come bundled with the utility libraries AsgardOS doesn't ship (Eden won't mix the two).
PKG_CMAKE_OPTS_TARGET="-DCMAKE_BUILD_TYPE=Release \
                       -DVulkanHeaders_FORCE_BUNDLED=ON \
                       -DENABLE_QT=ON \
                       -DENABLE_QT_TRANSLATION=OFF \
                       -DENABLE_UPDATE_CHECKER=OFF \
                       -DENABLE_WEB_SERVICE=OFF \
                       -DUSE_DISCORD_PRESENCE=OFF \
                       -DYUZU_USE_QT_WEB_ENGINE=OFF \
                       -DYUZU_USE_QT_MULTIMEDIA=OFF \
                       -DYUZU_USE_BUNDLED_QT=OFF \
                       -DYUZU_USE_BUNDLED_SDL2=OFF \
                       -DYUZU_USE_BUNDLED_FFMPEG=OFF \
                       -DYUZU_CMD=OFF \
                       -DYUZU_ROOM=OFF \
                       -DYUZU_ROOM_STANDALONE=OFF \
                       -DYUZU_TESTS=OFF \
                       -DYUZU_DISABLE_LLVM=ON"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/bin
    cp -a ${PKG_BUILD}/.${TARGET_NAME}/bin/eden ${INSTALL}/usr/bin
    cp -a ${PKG_DIR}/scripts/start_eden.sh ${INSTALL}/usr/bin

  mkdir -p ${INSTALL}/usr/config/eden
    cp -a ${PKG_DIR}/config/* ${INSTALL}/usr/config/eden
}
