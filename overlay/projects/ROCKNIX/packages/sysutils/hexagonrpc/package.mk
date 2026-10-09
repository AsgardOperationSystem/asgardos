# SPDX-License-Identifier: GPL-2.0
# HexagonRPC: FastRPC reverse-tunnel daemon. Serves the ADSP sensors PD its files (registry, configs) so the
# sensor core's QMI service (svc 400) comes up; the Thor's gyro/accel live there.

PKG_NAME="hexagonrpc"
PKG_VERSION="db659bdd117337766846bb6804a4453b6db06925"  # 0.6.0 Rust rewrite
PKG_SHA256="f19a2cd772d1e5dda083762b3e363e12a7c59f495bb10a62eec0f93db10cb3a1"
PKG_LICENSE="GPL-3.0-or-later"
PKG_SITE="https://github.com/lzxcr/hexagonrpc"
PKG_URL="${PKG_SITE}/archive/${PKG_VERSION}.tar.gz"
PKG_DEPENDS_TARGET="toolchain cargo:host"
PKG_LONGDESC="FastRPC reverse-tunnel daemon (hexagonrpcd) for Qualcomm DSP static PDs"
PKG_TOOLCHAIN="manual"

make_target() {
  cargo build --target ${TARGET_NAME} --release --locked -p hexagonrpcd
}

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/bin
  cp ${PKG_BUILD}/.${TARGET_NAME}/target/${TARGET_NAME}/release/hexagonrpcd ${INSTALL}/usr/bin/
}
