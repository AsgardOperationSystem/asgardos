# SPDX-License-Identifier: GPL-2.0
# Skyscraper: the game-media scraper RetroPie ships. asgard-scrape.py runs it for one game when the user has signed in to
# ScreenScraper (Settings > Library > ScreenScraper account): descriptions, Switch, and art libretro lacks (SCRAPE-1).
# Skyscraper carries its own ScreenScraper developer ID, so a user needs only their own free account. Built with qmake6
# against the image's Qt 6 (core, network, sql, xml), the way moonlight-qt is.

PKG_NAME="skyscraper"
PKG_VERSION="3.21.1"
PKG_SHA256="8f81cbd9f84b707ee107a50febbc3a5d7dc5b4e5d0bdecb00c37b3d6f2237852"
PKG_LICENSE="GPL-3.0"
PKG_SITE="https://github.com/Gemba/skyscraper"
PKG_URL="${PKG_SITE}/archive/refs/tags/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET="toolchain qt6"
PKG_LONGDESC="Skyscraper game-media scraper (ScreenScraper and others)"
PKG_TOOLCHAIN="manual"

make_target() {
  # As moonlight-qt: the cross compilers for qmake, and a qt.conf with the target prefix inside the sysroot.
  cat > ${PKG_BUILD}/.qmake.conf <<EOT
QMAKE_CC = ${CC}
QMAKE_CXX = ${CXX}
QMAKE_LINK = ${CXX}
QMAKE_LINK_SHLIB = ${CXX}
QMAKE_AR = ${AR} cqs
QMAKE_STRIP = ${STRIP}
EOT
  cat > ${PKG_BUILD}/target_qt.conf <<EOT
[Paths]
Prefix=/usr
HostPrefix=${TOOLCHAIN}/usr/local/qt6
HostData=${SYSROOT_PREFIX}/usr
Sysroot=${SYSROOT_PREFIX}
SysrootifyPrefix=true
TargetSpec=linux-g++
HostSpec=linux-g++
EOT
  # Its platform tables and default configs go to /etc/skyscraper (read-only); it copies them to ~/.skyscraper
  # (/storage/.skyscraper) on first run.
  PREFIX=/usr SYSCONFDIR=/etc ${TOOLCHAIN}/usr/local/qt6/bin/qmake6 -qtconf ${PKG_BUILD}/target_qt.conf skyscraper.pro
  make -j${CONCURRENCY_MAKE_LEVEL}
}

makeinstall_target() {
  make install INSTALL_ROOT=${INSTALL}
  rm -f ${INSTALL}/usr/bin/*.py ${INSTALL}/usr/bin/*.sh ${INSTALL}/usr/bin/*.md   # its maintainer scripts
  # Asgard's art: the plain cover, screenshot and wheel (marquee) Home shows, not the default composited montage.
  cp ${PKG_DIR}/config/asgard-artwork.xml ${INSTALL}/etc/skyscraper/
}
