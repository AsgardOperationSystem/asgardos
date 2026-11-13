# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS

PKG_NAME="switch-cheats-db"
PKG_VERSION="109766ab21c784150287c83ff85c02ab9512dccb" # master, 2026-10-17
PKG_SHA256="29529d9bbce095d1572302ff30b263d46234619d1be59b06769586f2d2c9f8ea"
PKG_LICENSE="none stated (community cheats from GBAtemp and others; bundled by the owner's choice, CHEAT-1)"
PKG_SITE="https://github.com/HamletDuFromage/switch-cheats-db"
PKG_URL="${PKG_SITE}/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET=""
PKG_LONGDESC="Switch cheats per title ID for asgard-cheats.py: cheats/<title ID>.json, {build ID: {\"[name]\": code}}"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/asgard-cheats/switch
    cp -a ${PKG_BUILD}/cheats/*.json ${INSTALL}/usr/share/asgard-cheats/switch/
}
