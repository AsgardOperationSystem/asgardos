# SPDX-License-Identifier: GPL-2.0
# An older Turnip (Mesa's Vulkan driver for Adreno) beside the image's Mesa, for the per-game "GPU driver" emulator
# option: the 3DS Zeldas run on it. Same build as tools/turnip/turnip.sh, installed to /usr/lib/gpu-drivers/<name>/.

PKG_NAME="turnip-extra"
PKG_VERSION="25.3.6"
PKG_SHA256="56db7261ca5c132d143ab32098192670b9f9d0e54e4799f009387262b6297153"
PKG_LICENSE="OSS"
PKG_SITE="http://www.mesa3d.org/"
PKG_URL="https://gitlab.freedesktop.org/mesa/mesa/-/archive/mesa-${PKG_VERSION}/mesa-mesa-${PKG_VERSION}.tar.gz"
PKG_SOURCE_DIR="mesa-mesa-${PKG_VERSION}"
PKG_DEPENDS_TARGET="toolchain expat libdrm Mako:host pyyaml:host wayland wayland-protocols libxcb libX11 libxshmfence libXrandr xorgproto"
PKG_LONGDESC="Turnip ${PKG_VERSION}, an extra Vulkan driver for the per-game GPU driver option"
PKG_TOOLCHAIN="meson"

PKG_MESON_OPTS_TARGET="-Dc_link_args=-lgcc -Dcpp_link_args=-lgcc \
                       -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm -Dgallium-drivers= -Dplatforms=wayland,x11 \
                       -Dopengl=false -Degl=disabled -Dgbm=disabled -Dglx=disabled -Dgles1=disabled -Dgles2=disabled \
                       -Dllvm=disabled -Dshader-cache=enabled -Dvideo-codecs= -Dbuild-tests=false -Dvalgrind=disabled \
                       -Dlibunwind=disabled -Dlmsensors=disabled -Dmicrosoft-clc=disabled"

PKG_MAKE_OPTS_TARGET="src/freedreno/vulkan/libvulkan_freedreno.so src/freedreno/vulkan/freedreno_icd.aarch64.json"

# Not ninja install: that would put a second libvulkan_freedreno.so and ICD over the image's Mesa.
makeinstall_target() {
  local DIR=/usr/lib/gpu-drivers/mesa-${PKG_VERSION}
  mkdir -p ${INSTALL}${DIR}
  cp src/freedreno/vulkan/libvulkan_freedreno.so ${INSTALL}${DIR}/
  sed "s|\"library_path\": \"[^\"]*\"|\"library_path\": \"${DIR}/libvulkan_freedreno.so\"|" \
    src/freedreno/vulkan/freedreno_icd.aarch64.json > ${INSTALL}${DIR}/icd.json
  echo "mesa-${PKG_VERSION}" > ${INSTALL}${DIR}/version
}
