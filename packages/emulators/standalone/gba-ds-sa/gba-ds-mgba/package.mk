# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS (https://github.com/AsgardOperationSystem)

# mGBA's source at the commit GBA DS builds against (its scripts/mgba-options.sh, MGBA_COMMIT).
# Unpacked only: gba-ds-sa builds libmgba from it and links it in statically.
PKG_NAME="gba-ds-mgba"
PKG_VERSION="143adf5aa2a60c6036810b0cd72445e13d74b0e6"
PKG_SHA256="32d73531d0fe743cfb27c0e11fb4869d495f6fd6a0162353fb73e29c26af64a7"
PKG_LICENSE="MPL-2.0"
PKG_SITE="https://github.com/mgba-emu/mgba"
PKG_URL="${PKG_SITE}/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET="toolchain"
PKG_LONGDESC="mGBA's source, for GBA DS (built into gba-ds-sa)"
PKG_TOOLCHAIN="manual"

make_target() {
  :
}

makeinstall_target() {
  :
}
