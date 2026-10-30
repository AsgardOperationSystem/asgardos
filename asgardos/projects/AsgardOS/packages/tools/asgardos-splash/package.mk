# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2025 ROCKNIX (https://github.com/ROCKNIX)
# AsgardOS: the boot splash, forked from ROCKNIX's asgardos-splash (9d295bc). Source lives next to this file in src/.

PKG_NAME="asgardos-splash"
PKG_VERSION="1.0"
PKG_LICENSE="GPL"
PKG_SITE="https://github.com/AsgardOperationSystem/asgardos"
PKG_DEPENDS_INIT="toolchain"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="AsgardOS splash screen application"

unpack() {
  mkdir -p ${PKG_BUILD}
  cp -a ${PKG_DIR}/src/. ${PKG_BUILD}/
}
