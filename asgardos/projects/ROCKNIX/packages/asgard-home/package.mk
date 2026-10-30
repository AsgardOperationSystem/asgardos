# SPDX-License-Identifier: GPL-2.0
# Asgard Home: the Asgard OS frontend (Qt Quick, dual-screen). Source lives next to this file in src/.

PKG_NAME="asgard-home"
PKG_VERSION="0.1"
PKG_LICENSE="GPL-2.0"
PKG_SITE="https://github.com/AsgardOperationSystem/asgardos"
PKG_DEPENDS_TARGET="toolchain qt6 layer-shell-qt es-theme-art-book-next"  # system artwork + logos
PKG_LONGDESC="Asgard Home: iiSU-style dual-screen game frontend"
PKG_TOOLCHAIN="cmake"

unpack() {
  mkdir -p ${PKG_BUILD}
  cp -a ${PKG_DIR}/src/. ${PKG_BUILD}/
}

# The frontend's font for the rest of the system too (mako's volume/brightness slider).
post_makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/fonts/nunito
  cp ${PKG_BUILD}/qml/fonts/*.ttf ${INSTALL}/usr/share/fonts/nunito/
}
