# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2026-present Asgard OS

PKG_NAME="asgard-library-manager"
PKG_VERSION="a79ea5177f67d5e9fdef216ab586b6bc852888c3" # main, 2026-11-21
PKG_SHA256="b7e09cb45c7d32c7188a141f79561065c22483b3f8e1207f55d6a260b4b1ae49"
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
