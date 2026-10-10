# SPDX-License-Identifier: GPL-2.0
# Asgard OS layer for the AYN Thor: its own scripts, services and apps on top of ROCKNIX.

PKG_NAME="asgard"
PKG_VERSION="1"
PKG_LICENSE="GPL-2.0"
PKG_SITE="https://github.com/AsgardOperationSystem/asgardos"
PKG_DEPENDS_TARGET="toolchain Python3 SDL2 SDL2_ttf SDL2_image asgard-home hexagonrpc rocknix-splash"
PKG_LONGDESC="Asgard OS layer for the AYN Thor"
PKG_TOOLCHAIN="manual"

# autostart/, system.d/ and sleep.d/ are installed by ROCKNIX's scripts/install (to autostart/common,
# systemd/system and systemd/system-sleep).
makeinstall_target() {
  mkdir -p ${INSTALL}/usr/share/asgard
  cp -r ${PKG_DIR}/sources/* ${INSTALL}/usr/share/asgard/
  chmod 0755 ${INSTALL}/usr/share/asgard/*.sh ${INSTALL}/usr/share/asgard/*.py

  # ROCKNIX's emulator option catalogue (Thor Settings → Game/System Options), without installing ROCKNIX ES.
  cp $(get_pkg_directory emulationstation)/config/common/es_features.cfg ${INSTALL}/usr/share/asgard/

  mkdir -p ${INSTALL}/usr/lib/systemd/system/sway.service.d
  cp ${PKG_DIR}/system.d/asgard-rotate.conf ${INSTALL}/usr/lib/systemd/system/sway.service.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/system/fancontrol.service.d
  cp ${PKG_DIR}/fancontrol.service.d/*.conf ${INSTALL}/usr/lib/systemd/system/fancontrol.service.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/logind.conf.d
  cp ${PKG_DIR}/logind.conf.d/*.conf ${INSTALL}/usr/lib/systemd/logind.conf.d/

  mkdir -p ${INSTALL}/usr/share/pipewire/pipewire.conf.d
  cp ${PKG_DIR}/pipewire/*.conf ${INSTALL}/usr/share/pipewire/pipewire.conf.d/
}

post_install() {
  for unit in asgard-bootanim essway thor-ayn-button thor-battery-log thor-display-sleep thor-idle-blank thor-sensorspd; do
    enable_service ${unit}.service
  done
}
