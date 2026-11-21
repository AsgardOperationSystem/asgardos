# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS

PKG_NAME="asgard-library-manager"
PKG_VERSION="b9c85d49b0bd91d330d887732ac0c5f5ff7103d5" # main, 2026-11-21
PKG_SHA256="" # set from the first download: GitHub makes the archive once the repo is pushed
PKG_LICENSE="GPL-2.0"
PKG_SITE="https://github.com/AsgardOperationSystem/asgard-library-manager"
PKG_URL="${PKG_SITE}/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET=""
PKG_LONGDESC="The Library Manager web app (LIB-1): one HTML file, served by asgard-library.py at http://<the Thor>:8467/"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/asgard-library-manager
  cp -a ${PKG_BUILD}/index.html ${INSTALL}/usr/share/asgard-library-manager/
}
