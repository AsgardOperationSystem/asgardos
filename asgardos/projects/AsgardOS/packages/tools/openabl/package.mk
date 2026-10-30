# SPDX-License-Identifier: GPL-2.0
# AsgardOS: OpenABL, an open-source boot menu + Boot Loader Spec boot built into Qualcomm's ABL (GPL-3.0).
# files/abl_signed-SM8550.elf is OpenABL v1.2 (ae7dad0) + source-patches/, built with OpenABL's ./build.sh sm8550
# and signed like the release (qtestsign root 8ffc3d64...). Installed to /usr/share/bootloader/openabl only: nothing
# flashes it (updateabl does, by hand, after a backup).

PKG_NAME="openabl"
PKG_VERSION="1.2-asgardos1"
PKG_LICENSE="GPL-3.0"
PKG_SITE="https://github.com/OpenHandheldCollective/OpenABL"
PKG_URL=""
PKG_LONGDESC="OpenABL: an open-source boot loader for Qualcomm handhelds"
PKG_TOOLCHAIN="manual"

makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/bootloader/openabl
    cp -a ${PKG_DIR}/files/abl_signed-SM8550.elf* ${INSTALL}/usr/share/bootloader/openabl/
  # The power-on picture (OpenABL > Custom boot logo, on by default in our build): an uncompressed 24-bit BMP in
  # \logo on the boot drive.
  mkdir -p ${INSTALL}/usr/share/bootloader/logo
    gzip -dc ${PKG_DIR}/logo/asgardos.bmp.gz > ${INSTALL}/usr/share/bootloader/logo/asgardos.bmp
}
