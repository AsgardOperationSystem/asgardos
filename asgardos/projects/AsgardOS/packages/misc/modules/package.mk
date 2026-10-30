# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2024-present ROCKNIX (https://github.com/ROCKNIX)

PKG_NAME="modules"
PKG_VERSION="1.0"
PKG_LICENSE="custom"
PKG_SITE=""
PKG_URL=""
PKG_DEPENDS_TARGET="toolchain rclone commander"
PKG_LONGDESC="OS Modules Package"
PKG_TOOLCHAIN="manual"

PKG_DEPENDS_TARGET+=" gamepadtester qterminal"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/config/modules
    cp -rf ${PKG_DIR}/sources/* ${INSTALL}/usr/config/modules
}

post_makeinstall_target() {

  if [[ "${INSTALLER_SUPPORT}" != "yes" || "${DISPLAYSERVER}" != "wl" ]]; then
    rm -f ${INSTALL}/usr/config/modules/Install*
  fi
}
