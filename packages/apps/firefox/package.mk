# SPDX-License-Identifier: GPL-2.0
# Firefox ESR: Mozilla's official linux-aarch64 build (every library it needs is already in the image: GTK3, NSS, EGL).

PKG_NAME="firefox"
PKG_VERSION="153.5.0esr"
PKG_SHA256="6579949c1d2d98f0d045cec780fa24752b57984f6e52d189ccfe003cf97f3d0b"
PKG_LICENSE="MPL-2.0"
PKG_SITE="https://www.mozilla.org/firefox/enterprise/"
PKG_URL="https://ftp.mozilla.org/pub/firefox/releases/${PKG_VERSION}/linux-aarch64/en-US/firefox-${PKG_VERSION}.tar.xz"
PKG_SOURCE_DIR="firefox"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Firefox ESR web browser"
PKG_TOOLCHAIN="manual"
PKG_BUILD_FLAGS="-strip"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/lib ${INSTALL}/usr/bin
  cp -a ${PKG_BUILD}/. ${INSTALL}/usr/lib/firefox/
  cp ${PKG_DIR}/sources/asgard-prefs.js ${INSTALL}/usr/lib/firefox/defaults/pref/
  cp ${PKG_DIR}/sources/start_firefox.sh ${INSTALL}/usr/bin/
  chmod 0755 ${INSTALL}/usr/bin/start_firefox.sh
}
