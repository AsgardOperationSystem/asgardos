# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS

PKG_NAME="ps2-cheats-db"
PKG_VERSION="6cb57b55939f47dd91a157bfb6cdc7fd157a780c" # main, 2024-08-28
PKG_SHA256="418b1381eb0b9f11698abc6d43835a09a5d61cf1141624c4d0a0b10179070678"
PKG_LICENSE="none stated (codes from Ultimate PCSX2 Cheater and CheatDevicePS2; bundled by the owner's choice, CHEAT-1)"
PKG_SITE="https://github.com/xs1l3n7x/pcsx2_cheats_collection"
PKG_URL="${PKG_SITE}/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET=""
PKG_LONGDESC="PS2 cheats per game for asgard-cheats.py: [<serial>_]<ELF CRC>.pnach, decrypted, one [name] group per cheat"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/asgard-cheats/ps2
    cp -a ${PKG_BUILD}/cheats/*.pnach ${INSTALL}/usr/share/asgard-cheats/ps2/
}
