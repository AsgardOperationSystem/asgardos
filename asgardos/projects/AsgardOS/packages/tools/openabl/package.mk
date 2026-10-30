# SPDX-License-Identifier: GPL-2.0
# AsgardOS: OpenABL, an open-source boot menu + Boot Loader Spec boot built into Qualcomm's ABL (GPL-3.0).
# Installed to /usr/share/bootloader/openabl only: nothing flashes it. Flash abl_a/abl_b by hand after a backup.

PKG_NAME="openabl"
PKG_VERSION="1.2"
PKG_SHA256="28cb97d1b387f28ddba28ed57fdc7d8b1c2ac2cdcd26af9c672620d41abddd4f"
PKG_LICENSE="GPL-3.0"
PKG_SITE="https://github.com/OpenHandheldCollective/OpenABL"
PKG_URL="${PKG_SITE}/releases/download/v${PKG_VERSION}/openabl-v${PKG_VERSION}.tar.gz"
PKG_LONGDESC="OpenABL: an open-source boot loader for Qualcomm handhelds"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/bootloader/openabl
    cp -a ${PKG_BUILD}/${DEVICE}/abl_signed-${DEVICE}.elf* ${INSTALL}/usr/share/bootloader/openabl/
}
