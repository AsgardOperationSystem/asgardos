# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2009-2016 Stephan Raue (stephan@openelec.tv)
# Copyright (C) 2017-present Team LibreELEC (https://libreelec.tv)

PKG_NAME="linux"
PKG_LICENSE="GPL"
PKG_SITE="http://www.kernel.org"
PKG_DEPENDS_HOST="ccache:host openssl:host"
PKG_DEPENDS_TARGET="linux:host kmod:host xz:host keyutils ncurses openssl:host ${KERNEL_EXTRA_DEPENDS_TARGET}"
PKG_NEED_UNPACK="${LINUX_DEPENDS} $(get_pkg_directory initramfs) $(get_pkg_variable initramfs PKG_NEED_UNPACK)"
PKG_NEED_UNPACK+=" ${PROJECT_PATH}/bootloader ${DEVICE_PATH}/bootloader"
# The boot entry carries DISTRO_BOOTLABEL/DISTRO_DISKLABEL (makeinstall_target): rebuild when the options change.
PKG_NEED_UNPACK+=" ${DISTRO_PATH}/options"
PKG_LONGDESC="This package contains a precompiled kernel image and the modules."
PKG_IS_KERNEL_PKG="yes"
PKG_STAMP="${KERNEL_TARGET} ${KERNEL_MAKE_EXTRACMD}"

# Our kernel fork, the submodule src/ (gitlab asgardos/linux, branch asgard): Linux stable plus
# the Asgard patches and device trees as commits. Rebuilds when src/ changes (it's hashed with PKG_DIR).
PKG_VERSION="7.3.5"
PKG_PATCH_DIRS=""

PKG_KERNEL_CFG_FILE=$(kernel_config_path) || die

if [ -n "${KERNEL_TOOLCHAIN}" ]; then
  PKG_DEPENDS_TARGET+=" gcc-${KERNEL_TOOLCHAIN}:host"
  HEADERS_ARCH=${TARGET_ARCH}
else
  PKG_DEPENDS_TARGET+=" toolchain"
fi

if [ "${PKG_BUILD_PERF}" != "no" ] && grep -q ^CONFIG_PERF_EVENTS= ${PKG_KERNEL_CFG_FILE}; then
  PKG_BUILD_PERF="yes"
  PKG_DEPENDS_TARGET+=" binutils elfutils libunwind zlib openssl"
fi

if [[ "${TARGET_ARCH}" =~ i*86|x86_64 ]]; then
  PKG_DEPENDS_TARGET+=" elfutils:host pciutils"
  PKG_DEPENDS_UNPACK+=" intel-ucode kernel-firmware"
fi

# Ensure that the dependencies of initramfs:target are built correctly, but
# we don't want to add initramfs:target as a direct dependency as we install
# this "manually" from within linux:target
for pkg in $(get_pkg_variable initramfs PKG_DEPENDS_TARGET); do
  ! listcontains "${PKG_DEPENDS_TARGET}" "${pkg}" && PKG_DEPENDS_TARGET+=" ${pkg}" || true
done

# A built-in cfg80211 needs regulatory.db inside the kernel image (see
# pre_make_target), so unpack wireless-regdb before the kernel is built.
if grep -q '^CONFIG_CFG80211=y' ${PKG_KERNEL_CFG_FILE}; then
  PKG_DEPENDS_UNPACK+=" wireless-regdb"
fi

# SM8550: copy the kernel submodule (the build container has no access to its .git).
if [ "${DEVICE}" = "SM8550" ]; then
  unpack() {
    [ -f "${PKG_DIR}/src/Makefile" ] || die "linux: src/ is empty, run: git submodule update --init"
    mkdir -p ${PKG_BUILD}
    rsync -a --exclude=.git ${PKG_DIR}/src/ ${PKG_BUILD}/
  }
fi

post_patch() {
  # linux was already built and its build dir autoremoved - prepare it again for kernel packages
  if [ -d ${PKG_INSTALL}/.image ]; then
    cp -p ${PKG_INSTALL}/.image/.config ${PKG_BUILD}
    kernel_make -C ${PKG_BUILD} prepare

    # restore the required Module.symvers from an earlier build
    cp -p ${PKG_INSTALL}/.image/Module.symvers ${PKG_BUILD}
  fi
}

make_init() {
 : # reuse make_target()
}

makeinstall_init() {
  :
}

make_host() {
  :
}

makeinstall_host() {
  make \
    ARCH=${HEADERS_ARCH:-${TARGET_KERNEL_ARCH}} \
    HOSTCC="${TOOLCHAIN}/bin/host-gcc" \
    HOSTCXX="${TOOLCHAIN}/bin/host-g++" \
    HOSTCFLAGS="${HOST_CFLAGS}" \
    HOSTCXXFLAGS="${HOST_CXXFLAGS}" \
    HOSTLDFLAGS="${HOST_LDFLAGS}" \
    INSTALL_HDR_PATH=dest \
    headers_install
  mkdir -p ${SYSROOT_PREFIX}/usr/include
    cp -R dest/include/* ${SYSROOT_PREFIX}/usr/include
}

pre_make_target() {
  ( cd ${ROOT}
    rm -rf ${BUILD}/initramfs
    rm -f ${STAMPS_INSTALL}/initramfs/install_target ${STAMPS_INSTALL}/*/install_init
    ${SCRIPTS}/install initramfs
  )
  pkg_lock_status "ACTIVE" "linux:target" "build"

  cp ${PKG_KERNEL_CFG_FILE} ${PKG_BUILD}/.config

  # set initramfs source
  ${PKG_BUILD}/scripts/config --set-str CONFIG_INITRAMFS_SOURCE "$(kernel_initramfs_confs) ${BUILD}/initramfs"

  # set default hostname based on ${DISTRONAME}
  ${PKG_BUILD}/scripts/config --set-str CONFIG_DEFAULT_HOSTNAME "${DISTRONAME}"

  # disable swap support if not enabled
  if [ ! "${SWAP_SUPPORT}" = yes ]; then
    ${PKG_BUILD}/scripts/config --disable CONFIG_SWAP
  fi

  # disable nfs support if not enabled
  if [ "${NFS_SUPPORT}" = no ]; then
    ${PKG_BUILD}/scripts/config --disable CONFIG_NFS_FS
  fi

  # disable cifs support if not enabled
  if [ ! "${SAMBA_SUPPORT}" = yes ]; then
    ${PKG_BUILD}/scripts/config --disable CONFIG_CIFS
  fi

  # disable iscsi support if not enabled
  if [ ! "${ISCSI_SUPPORT}" = yes ]; then
    ${PKG_BUILD}/scripts/config --disable CONFIG_SCSI_ISCSI_ATTRS
    ${PKG_BUILD}/scripts/config --disable CONFIG_ISCSI_TCP
    ${PKG_BUILD}/scripts/config --disable CONFIG_ISCSI_BOOT_SYSFS
    ${PKG_BUILD}/scripts/config --disable CONFIG_ISCSI_IBFT_FIND
    ${PKG_BUILD}/scripts/config --disable CONFIG_ISCSI_IBFT
  fi

  # disable lima/panfrost if libmali is configured
  if [ "${OPENGLES}" = "libmali" ]; then
    ${PKG_BUILD}/scripts/config --disable CONFIG_DRM_LIMA
    ${PKG_BUILD}/scripts/config --disable CONFIG_DRM_PANFROST
  fi

  # disable wireguard support if not enabled
  if [ ! "${WIREGUARD_SUPPORT}" = yes ]; then
    ${PKG_BUILD}/scripts/config --disable CONFIG_WIREGUARD
  fi

  # cfg80211 requests regulatory.db as soon as it initialises. Built in (=y on
  # every device but AMD64) that is during kernel init, while /usr/lib/firmware
  # is still a dangling symlink to the kernel-overlay tmpfs that
  # kernel-overlays-setup only populates later (scripts/image) - so the request
  # fails with -ENOENT, the failure is cached, and the radio stays in domain 00
  # with 5 GHz no-IR. Build the db into the kernel instead. The .p7s signature
  # goes with it because CONFIG_CFG80211_REQUIRE_SIGNED_REGDB is set. Appends to
  # whatever the per-device blocks above already listed (~7 KB in the image).
  if grep -q '^CONFIG_CFG80211=y' ${PKG_BUILD}/.config; then
    mkdir -p ${PKG_BUILD}/external-firmware
      cp -Lv $(get_build_dir wireless-regdb)/regulatory.db ${PKG_BUILD}/external-firmware
      cp -Lv $(get_build_dir wireless-regdb)/regulatory.db.p7s ${PKG_BUILD}/external-firmware

    FW_LIST="$(${PKG_BUILD}/scripts/config --state CONFIG_EXTRA_FIRMWARE)"
    [ "${FW_LIST}" = "undef" ] && FW_LIST=""

    ${PKG_BUILD}/scripts/config --set-str CONFIG_EXTRA_FIRMWARE \
      "$(echo ${FW_LIST} regulatory.db regulatory.db.p7s | xargs)"
    ${PKG_BUILD}/scripts/config --set-str CONFIG_EXTRA_FIRMWARE_DIR "external-firmware"
  fi

  kernel_make listnewconfig
  if [ "${INTERACTIVE_CONFIG}" = "yes" ]; then
    # manually answer .config changes
    kernel_make oldconfig
  elif [ "${INTERACTIVE_CONFIG}" = "menuconfig" ]; then
    # manually answer .config changes
    kernel_make menuconfig
  else
    # accept default answers for .config changes
    yes "" | kernel_make oldconfig > /dev/null
  fi

  if [ -f "${DISTRO_PATH}/kernel_options" ]; then
    while read OPTION; do
      [ -z "${OPTION}" -o -n "$(echo "${OPTION}" | grep '^#')" ] && continue

      if [ "${OPTION##*=}" == "n" -a "$(${PKG_BUILD}/scripts/config --state ${OPTION%%=*})" == "undef" ]; then
        continue
      fi

      if [ "$(${PKG_BUILD}/scripts/config --state ${OPTION%%=*})" != "$(echo ${OPTION##*=} | tr -d '"')" ]; then
        MISSING_KERNEL_OPTIONS+="\t${OPTION}\n"
      fi
    done < ${DISTRO_PATH}/kernel_options

    if [ -n "${MISSING_KERNEL_OPTIONS}" ]; then
      print_color CLR_WARNING "LINUX: kernel options not correct: \n${MISSING_KERNEL_OPTIONS%%}\nPlease run ./tools/check_kernel_config\n"
    fi
  fi
}

make_target() {
  DTC_FLAGS=-@ kernel_make ${KERNEL_TARGET} ${KERNEL_MAKE_EXTRACMD} modules

  if [ "${PKG_BUILD_PERF}" = "yes" ]; then
    ( cd tools/perf

      # arch specific perf build args
      case "${TARGET_ARCH}" in
        x86_64|i*86)
          PERF_BUILD_ARGS="ARCH=x86"
          ;;
        aarch64)
          PERF_BUILD_ARGS="ARCH=arm64"
          ;;
        *)
          PERF_BUILD_ARGS="ARCH=${TARGET_ARCH}"
          ;;
      esac

      export BUILD_BPF_SKEL=0

      WERROR=0 \
      NO_LIBPERL=1 \
      NO_LIBPYTHON=1 \
      NO_SLANG=1 \
      NO_GTK2=1 \
      NO_LIBNUMA=1 \
      NO_LIBAUDIT=1 \
      NO_LIBTRACEEVENT=1 \
      NO_LZMA=1 \
      NO_SDT=1 \
      NO_LIBDEBUGINFOD=1 \
      NO_JVMTI=1 \
      NO_LIBLLVM=1 \
      NO_LIBPFM4=1 \
      NO_LIBBABELTRACE=1 \
      NO_CAPSTONE=1 \
      NO_RUST=1 \
      CROSS_COMPILE="${TARGET_PREFIX}" \
      JOBS="${CONCURRENCY_MAKE_LEVEL}" \
      EXTRA_CFLAGS="-g -O2 -Wno-error=discarded-qualifiers" \
        make ${PERF_BUILD_ARGS}
      mkdir -p ${INSTALL}/usr/bin
        cp perf ${INSTALL}/usr/bin
    )
  fi
}

makeinstall_target() {
  mkdir -p ${INSTALL}/.image
  cp -p System.map .config Module.symvers ${INSTALL}/.image/

  cp -p arch/${TARGET_KERNEL_ARCH}/boot/${KERNEL_TARGET} ${INSTALL}/.image/

  if [ "${BOOTLOADER}" = "qcom-abl" ]; then
    # AsgardOS boots through OpenABL (Boot Loader Spec): KERNEL is the plain kernel, started by its EFI stub (the
    # initramfs is built in), with the device trees and an entry naming the Thor's, so OpenABL's Device model
    # setting doesn't matter.
    mkdir -p ${INSTALL}/usr/share/bootloader/dtbs ${INSTALL}/usr/share/bootloader/loader/entries
    cp arch/${TARGET_KERNEL_ARCH}/boot/dts/qcom/*.dtb ${INSTALL}/usr/share/bootloader/dtbs/
    cat > ${INSTALL}/usr/share/bootloader/loader/entries/asgardos.conf <<BLS
title      ${DISTRONAME}
linux      /KERNEL
devicetree /dtbs/qcs8550-ayn-thor.dtb
options    boot=LABEL=${DISTRO_BOOTLABEL} disk=LABEL=${DISTRO_DISKLABEL} ${EXTRA_CMDLINE}
BLS
  fi

  kernel_make INSTALL_MOD_PATH=${INSTALL}/$(get_kernel_overlay_dir) modules_install
  rm -f ${INSTALL}/$(get_kernel_overlay_dir)/lib/modules/*/build
  rm -f ${INSTALL}/$(get_kernel_overlay_dir)/lib/modules/*/source
}
