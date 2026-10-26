# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2024-present ROCKNIX (https://github.com/ROCKNIX)

PKG_NAME="nestopia-lr"
PKG_VERSION="2110d21b7174455ec98948bb474147dea0e3cad0"
PKG_SHA256="ed83409b97a547bd3619f830d3033222169c970669cc97353dd6ede30025b160"
PKG_LICENSE="GPL-2.0-or-later"
PKG_SITE="https://github.com/libretro/nestopia"
PKG_URL="${PKG_SITE}/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="Libretro implementation of NEStopia. (Nintendo Entertainment System)"
PKG_TOOLCHAIN="make"

PKG_MAKE_OPTS_TARGET="-C libretro"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/lib/libretro
    cp -a libretro/nestopia_libretro.so ${INSTALL}/usr/lib/libretro
}
