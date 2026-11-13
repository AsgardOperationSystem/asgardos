# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS

PKG_NAME="asgard-cheats-db"
PKG_VERSION="aeab5fd3b001ed22c013efd1a02b092575d825ed" # FlagBrew/Sharkive master, 2026-08-23
PKG_SHA256="9bde9bf287e77f95efe134907620248bf06afec7a4caaa0280536188fea94145"
PKG_LICENSE="GPL-3.0"
PKG_SITE="https://github.com/FlagBrew/Sharkive"
PKG_URL="${PKG_SITE}/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET=""
PKG_LONGDESC="Cheat databases for asgard-cheats.py (CHEAT-1): 3DS from Sharkive (Citra format, 3ds/<title ID>.txt)"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/asgard-cheats/3ds
    cp -a ${PKG_BUILD}/3ds/*.txt ${INSTALL}/usr/share/asgard-cheats/3ds/
}
