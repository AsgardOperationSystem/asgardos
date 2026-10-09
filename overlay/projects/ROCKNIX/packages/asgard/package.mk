# SPDX-License-Identifier: GPL-2.0
# Asgard OS layer for the AYN Thor: its own scripts, services and apps on top of ROCKNIX.

PKG_NAME="asgard"
PKG_VERSION="1"
PKG_LICENSE="GPL-2.0"
PKG_SITE="https://github.com/AsgardOperationSystem/asgardos"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Asgard OS layer for the AYN Thor"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/lib/autostart/common
  cp ${PKG_DIR}/autostart/* ${INSTALL}/usr/lib/autostart/common/
  chmod 0755 ${INSTALL}/usr/lib/autostart/common/*-asgard-*
}
