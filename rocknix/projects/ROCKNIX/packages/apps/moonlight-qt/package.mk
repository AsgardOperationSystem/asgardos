# SPDX-License-Identifier: GPL-2.0
# Moonlight (moonlight-qt): the game-streaming client's full GUI (pairing, hosts, apps, settings; controller and touch)
# for Tools > Moonlight. ROCKNIX ships moonlight-embedded (/usr/bin/moonlight, command line only, its Moonlight system);
# this one installs as /usr/bin/moonlight-qt beside it. Built from the release's source tarball (submodules included)
# against the image's Qt 6, SDL2, FFmpeg, libplacebo (Vulkan) and Wayland.

PKG_NAME="moonlight-qt"
PKG_VERSION="6.2.0"
PKG_SHA256="217afac54e4f8734f3d97b32cb8c8b46b677e87f25b77c945343dd06f359e189"
PKG_LICENSE="GPL-3.0"
PKG_SITE="https://github.com/moonlight-stream/moonlight-qt"
PKG_URL="${PKG_SITE}/releases/download/v${PKG_VERSION}/MoonlightSrc-${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET="toolchain qt6 SDL2 SDL2_ttf openssl opus ffmpeg libdrm libplacebo wayland"
PKG_LONGDESC="Moonlight game-streaming client (Qt GUI)"
PKG_TOOLCHAIN="manual"

# The tarball has no top-level folder.
unpack() {
  mkdir -p ${PKG_BUILD}
  tar -xzf ${SOURCES}/${PKG_NAME}/${PKG_NAME}-${PKG_VERSION}.tar.gz -C ${PKG_BUILD}
}

make_target() {
  # qmake's mkspec says gcc/g++/ar: the cross ones, for every subproject (.qmake.conf at the top is read by all; a
  # value with a space on the command line is split into two arguments).
  cat > ${PKG_BUILD}/.qmake.conf <<EOF
QMAKE_CC = ${CC}
QMAKE_CXX = ${CXX}
QMAKE_LINK = ${CXX}
QMAKE_LINK_SHLIB = ${CXX}
QMAKE_AR = ${AR} cqs
QMAKE_STRIP = ${STRIP}
EOF
  # The sysroot's target_qt.conf has a relative Prefix and SysrootifyPrefix: Qt's include paths got the sysroot twice.
  # Its own qt.conf, with the target prefix /usr inside the sysroot and the host qmake's mkspecs there too.
  cat > ${PKG_BUILD}/target_qt.conf <<EOF
[Paths]
Prefix=/usr
HostPrefix=${TOOLCHAIN}/usr/local/qt6
HostData=${SYSROOT_PREFIX}/usr
Sysroot=${SYSROOT_PREFIX}
SysrootifyPrefix=true
TargetSpec=linux-g++
HostSpec=linux-g++
EOF
  # embedded: always fullscreen, no window chrome (EMBEDDED_BUILD)
  ${TOOLCHAIN}/usr/local/qt6/bin/qmake6 -qtconf ${PKG_BUILD}/target_qt.conf PREFIX=/usr CONFIG+=embedded \
    CONFIG+=disable-libva CONFIG+=disable-libvdpau CONFIG+=disable-x11 moonlight-qt.pro
  make -j${CONCURRENCY_MAKE_LEVEL}
}

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/bin
  cp ${PKG_BUILD}/app/moonlight ${INSTALL}/usr/bin/moonlight-qt
  cp ${PKG_DIR}/sources/start_moonlight-qt.sh ${INSTALL}/usr/bin/
  chmod 0755 ${INSTALL}/usr/bin/moonlight-qt ${INSTALL}/usr/bin/start_moonlight-qt.sh
}
