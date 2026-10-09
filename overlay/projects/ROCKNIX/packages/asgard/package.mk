# SPDX-License-Identifier: GPL-2.0
# Asgard OS layer for the AYN Thor: its own scripts, services and apps on top of ROCKNIX.

PKG_NAME="asgard"
PKG_VERSION="1"
PKG_LICENSE="GPL-2.0"
PKG_SITE="https://github.com/AsgardOperationSystem/asgardos"
PKG_DEPENDS_TARGET="toolchain Python3"
PKG_LONGDESC="Asgard OS layer for the AYN Thor"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/asgard
  cp -r ${PKG_DIR}/sources/* ${INSTALL}/usr/share/asgard/
  chmod 0755 ${INSTALL}/usr/share/asgard/*.sh ${INSTALL}/usr/share/asgard/*.py

  mkdir -p ${INSTALL}/usr/lib/autostart/common
  cp ${PKG_DIR}/autostart/* ${INSTALL}/usr/lib/autostart/common/
  chmod 0755 ${INSTALL}/usr/lib/autostart/common/*-asgard-*

  mkdir -p ${INSTALL}/usr/lib/systemd/system/sway.service.d
  cp ${PKG_DIR}/system.d/*.service ${INSTALL}/usr/lib/systemd/system/
  cp ${PKG_DIR}/system.d/asgard-rotate.conf ${INSTALL}/usr/lib/systemd/system/sway.service.d/
}

post_install() {
  for unit in thor-display-sleep thor-idle-blank; do
    enable_service ${unit}.service
  done
}
