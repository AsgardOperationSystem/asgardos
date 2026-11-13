# SPDX-License-Identifier: GPL-2.0
# Asgard OS layer for the AYN Thor: its own scripts, services and apps on top of the base system.

PKG_NAME="asgard"
PKG_VERSION="1"
PKG_LICENSE="GPL-2.0"
PKG_SITE="https://github.com/AsgardOperationSystem/asgardos"
PKG_DEPENDS_TARGET="toolchain wayland Python3 SDL2 SDL2_ttf SDL2_image asgard-home firefox moonlight-qt hexagonrpc asgardos-splash turnip-extra asgard-cheats-db switch-cheats-db"
PKG_LONGDESC="Asgard OS layer for the AYN Thor"
PKG_TOOLCHAIN="manual"

# autostart/, system.d/ and sleep.d/ are installed by scripts/install (to autostart/common,
# systemd/system and systemd/system-sleep).
makeinstall_target() {
  # LÖVE ports run outside PortMaster (Gen1recomp's love.aarch64) need libtheoradec.so.1, which only PortMaster's
  # /usr/lib/compat ships (not on the linker path): without it they fail to start.
  mkdir -p ${INSTALL}/usr/lib
  ln -sf compat/libtheoradec.so.1 ${INSTALL}/usr/lib/libtheoradec.so.1

  mkdir -p ${INSTALL}/usr/share/asgard
  cp -r ${PKG_DIR}/sources/* ${INSTALL}/usr/share/asgard/
  # Bytecode from running the scripts on the build machine: its paths (home dir), and the Thor compiles its own.
  rm -rf ${INSTALL}/usr/share/asgard/__pycache__
  # Host tests (./test.sh) don't ship.
  rm -f ${INSTALL}/usr/share/asgard/test_*
  chmod 0755 ${INSTALL}/usr/share/asgard/*.sh ${INSTALL}/usr/share/asgard/*.py

  # ROCKNIX's emulator option catalogue (Thor Settings → Game/System Options), without installing ROCKNIX ES.
  cp $(get_pkg_directory emulationstation)/config/common/es_features.cfg ${INSTALL}/usr/share/asgard/

  mkdir -p ${INSTALL}/usr/lib/systemd/system/sway.service.d
  cp ${PKG_DIR}/system.d/asgard-rotate.conf ${INSTALL}/usr/lib/systemd/system/sway.service.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/system/sway-touch.service.d
  cp ${PKG_DIR}/sway-touch.service.d/*.conf ${INSTALL}/usr/lib/systemd/system/sway-touch.service.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/system/fancontrol.service.d
  cp ${PKG_DIR}/fancontrol.service.d/*.conf ${INSTALL}/usr/lib/systemd/system/fancontrol.service.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/system/inputplumber.service.d
  cp ${PKG_DIR}/inputplumber.service.d/*.conf ${INSTALL}/usr/lib/systemd/system/inputplumber.service.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/system/systemd-logind.service.d
  cp ${PKG_DIR}/systemd-logind.service.d/*.conf ${INSTALL}/usr/lib/systemd/system/systemd-logind.service.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/coredump.conf.d
  cp ${PKG_DIR}/coredump.conf.d/*.conf ${INSTALL}/usr/lib/systemd/coredump.conf.d/

  mkdir -p ${INSTALL}/usr/lib/systemd/logind.conf.d
  cp ${PKG_DIR}/logind.conf.d/*.conf ${INSTALL}/usr/lib/systemd/logind.conf.d/

  mkdir -p ${INSTALL}/usr/share/pipewire/pipewire.conf.d
  cp ${PKG_DIR}/pipewire/*.conf ${INSTALL}/usr/share/pipewire/pipewire.conf.d/

  # Speaker EQ "Joey" (asgard-eq.py): its impulse response and the limiter after its +15 dB.
  mkdir -p ${INSTALL}/usr/share/asgard/eq ${INSTALL}/usr/lib/ladspa
  cp ${PKG_DIR}/eq/joey-speaker.wav ${INSTALL}/usr/share/asgard/eq/
  ${CC} ${CFLAGS} -O2 -shared -fPIC ${LDFLAGS} -o ${INSTALL}/usr/lib/ladspa/asgard-limiter.so ${PKG_DIR}/eq/asgard-limiter.c -lm

  # Per-screen white balance (asgard-gamma.service): a wlr-gamma-control client holding each panel's ramp.
  wayland-scanner client-header ${PKG_DIR}/gamma/wlr-gamma-control-unstable-v1.xml ${PKG_BUILD}/wlr-gamma-control-unstable-v1-client-protocol.h
  wayland-scanner private-code ${PKG_DIR}/gamma/wlr-gamma-control-unstable-v1.xml ${PKG_BUILD}/wlr-gamma-control.c
  mkdir -p ${INSTALL}/usr/bin
  ${CC} ${CFLAGS} -O2 -I${PKG_BUILD} ${LDFLAGS} -o ${INSTALL}/usr/bin/asgard-gamma ${PKG_DIR}/gamma/asgard-gamma.c \
    ${PKG_BUILD}/wlr-gamma-control.c -lwayland-client -lm

  # Headphones outrank the speaker so the default output follows the jack (thor_dsp_* smart filters follow it).
  mkdir -p ${INSTALL}/usr/share/wireplumber/wireplumber.conf.d
  cp ${PKG_DIR}/wireplumber/*.conf ${INSTALL}/usr/share/wireplumber/wireplumber.conf.d/
}

post_install() {
  for unit in asgard-bootanim asgard-charge-limit asgard-gamma asgard-cores asgard-events asgard-lastboot essway thor-ayn-button thor-battery-log thor-bottom-touch thor-display-sleep thor-idle-blank thor-sensorspd; do
    enable_service ${unit}.service
  done
}
