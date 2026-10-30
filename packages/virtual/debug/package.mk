# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2009-2016 Stephan Raue (stephan@openelec.tv)
# Copyright (C) 2016-present Team LibreELEC (https://libreelec.tv)

PKG_NAME="debug"
PKG_VERSION=""
PKG_LICENSE="GPL-2.0-or-later"
PKG_SITE="https://www.libreelec.tv"
PKG_URL=""
PKG_DEPENDS_TARGET="toolchain gdb memtester strace kmsxx"
PKG_SECTION="virtual"
PKG_LONGDESC="debug is a Metapackage for installing debugging tools"

# configure GPU drivers and dependencies:
  get_graphicdrivers

if [ "${VAAPI_SUPPORT}" = "yes" ]; then
  PKG_DEPENDS_TARGET+=" libva-utils"
fi

if [ "${VALGRIND}" = "yes" ]; then
  PKG_DEPENDS_TARGET+=" valgrind"
fi

if [ "${REMOTE_GDB}" = "yes" ]; then
  PKG_DEPENDS_TARGET+=" gdb:host"
fi

# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2024-present ROCKNIX (https://github.com/ROCKNIX)
PKG_DEPENDS_TARGET+=" nvtop apitrace renderdoc"

# strace is broken on 6.19 kernels, so temporarily remove
PKG_DEPENDS_TARGET=${PKG_DEPENDS_TARGET//"strace"/}
