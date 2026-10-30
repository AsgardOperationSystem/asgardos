#!/bin/bash

# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2022-present JELOS (https://github.com/JustEnoughLinuxOS)

. /etc/profile
set_kill set "-9 flycast"

#load gptokeyb support files
control-gen_init.sh
source /storage/.config/gptokeyb/control.ini
get_controls

# Conf files vars
SOURCE_DIR="/usr/config/flycast"
CONF_DIR="/storage/.config/flycast"
FLYCAST_INI="emu.cfg"

#Check if flycast exists in .config
if [ ! -d "/storage/.config/flycast" ]; then
  cp -r "${SOURCE_DIR}" "${CONF_DIR}"
fi

#Restore a config emptied by a kill mid-save
if ! grep -q "^\[config\]" "${CONF_DIR}/${FLYCAST_INI}" 2>/dev/null; then
  cp "${SOURCE_DIR}/${FLYCAST_INI}" "${CONF_DIR}/${FLYCAST_INI}"
fi

#Move save file storage/roms
if [ -d "${CONF_DIR}/data" ]; then
  mv "${CONF_DIR}/data" "/storage/roms/dreamcast/"
fi

#Make flycast bios folder
if [ ! -d "/storage/roms/bios/dc" ]; then
  mkdir -p "/storage/roms/bios/dc"
fi

#Link  .config/flycast to .local
ln -sf "/storage/roms/bios/dc" "/storage/roms/dreamcast/data"


#Make sure flycast gptk config exists
if [ ! -f "${CONF_DIR}/flycast.gptk" ]; then
  cp -r "/usr/config/flycast/flycast.gptk" "${CONF_DIR}/flycast.gptk"
fi

#Make sure flycast gptk SDL_Keyboard.cfg exists
if [ ! -f "${CONF_DIR}/mappings/SDL_Keyboard.cfg" ]; then
  cp -r "/usr/config/flycast/mappings/SDL_Keyboard.cfg" "${CONF_DIR}/mappings/SDL_Keyboard.cfg"
fi

# Asgard: copies of the shipped mapping start with "digital]" (its "[" was missing), so Flycast skipped the section.
sed -i '1s/^digital\]$/[digital]/' "${CONF_DIR}/mappings/SDL_Keyboard.cfg"
# F1 opens Flycast's menu (as in AsgardOS's InputPlumber mapping); the Home button sends it (thor_ayn_button.py).
# Flycast reads bind0, bind1... in order, so it gets the next free number.
if ! grep -q ":btn_menu" "${CONF_DIR}/mappings/SDL_Keyboard.cfg"; then
  N=$(grep -c "^bind" "${CONF_DIR}/mappings/SDL_Keyboard.cfg")
  sed -i "/^\[digital\]/a bind${N} = 58:btn_menu" "${CONF_DIR}/mappings/SDL_Keyboard.cfg"
fi

#Emulation Station Features
GAME=$(echo "${1}"| sed "s#^/.*/##")
PLATFORM=$(echo "${2}"| sed "s#^/.*/##")
ASPECT=$(get_setting aspect_ratio "${PLATFORM}" "${GAME}")
ASKIP=$(get_setting auto_frame_skipping "${PLATFORM}" "${GAME}")
FPS=$(get_setting show_fps "${PLATFORM}" "${GAME}")
IRES=$(get_setting internal_resolution "${PLATFORM}" "${GAME}")
GRENDERER=$(get_setting graphics_backend "${PLATFORM}" "${GAME}")
VSYNC=$(get_setting vsync "${PLATFORM}" "${GAME}")

#Set the cores to use
CORES=$(get_setting "cores" "${PLATFORM}" "${GAME}")
if [ "${CORES}" = "little" ]
then
  EMUPERF="${SLOW_CORES}"
elif [ "${CORES}" = "big" ]
then
  EMUPERF="${FAST_CORES}"
else
  ### All..
  unset EMUPERF
fi

# Flycast's emu.cfg holds only what differs from its defaults: add the keys edited below (at Flycast's defaults)
# when missing, else their sed -i c\ edits change nothing.
for kv in rend.WideScreen=no rend.SuperWideScreen=no rend.ShowFPS=no rend.vsync=yes pvr.AutoSkipFrame=0 \
          rend.Resolution=480 rend.WidescreenGameHacks=no rend.IntegerScale=no; do
  grep -q "^${kv%%=*} =" "${CONF_DIR}/${FLYCAST_INI}" || sed -i "/^\[config\]/a ${kv%%=*} = ${kv#*=}" "${CONF_DIR}/${FLYCAST_INI}"
done

  #AspectRatio
        if [ "$ASPECT" = "w" ]; then
                sed -i '/^rend.WideScreen =/c\rend.WideScreen = yes' "${CONF_DIR}/${FLYCAST_INI}"
                sed -i '/^rend.SuperWideScreen =/c\rend.SuperWideScreen = no' "${CONF_DIR}/${FLYCAST_INI}"
        elif [ "$ASPECT" = "sw" ]; then
                sed -i '/^rend.WideScreen =/c\rend.WideScreen = yes' "${CONF_DIR}/${FLYCAST_INI}"
                sed -i '/^rend.SuperWideScreen =/c\rend.SuperWideScreen = yes' "${CONF_DIR}/${FLYCAST_INI}"
	else
		sed -i '/^rend.WideScreen =/c\rend.WideScreen = no' "${CONF_DIR}/${FLYCAST_INI}"
		sed -i '/^rend.SuperWideScreen =/c\rend.SuperWideScreen = no' "${CONF_DIR}/${FLYCAST_INI}"
        fi

  #AutoFrameSkip
        if [ "$ASKIP" = "normal" ]; then
                sed -i '/^pvr.AutoSkipFrame =/c\pvr.AutoSkipFrame = 1' "${CONF_DIR}/${FLYCAST_INI}"
        elif [ "$ASKIP" = "max" ]; then
                sed -i '/^pvr.AutoSkipFrame =/c\pvr.AutoSkipFrame = 2' "${CONF_DIR}/${FLYCAST_INI}"
	elif [ "$ASKIP" = "off" ]; then
		sed -i '/^pvr.AutoSkipFrame =/c\pvr.AutoSkipFrame = 0' "${CONF_DIR}/${FLYCAST_INI}"
        fi

  #Internal Resolution
        if [ "$IRES" = "0" ]; then
                sed -i '/rend.Resolution =/c\rend.Resolution = 240' "${CONF_DIR}/${FLYCAST_INI}"
        elif [ "$IRES" = "2" ]; then
                sed -i '/rend.Resolution =/c\rend.Resolution = 720' "${CONF_DIR}/${FLYCAST_INI}"
        elif [ "$IRES" = "3" ]; then
                sed -i '/rend.Resolution =/c\rend.Resolution = 960' "${CONF_DIR}/${FLYCAST_INI}"
        elif [ "$IRES" = "4" ]; then
                sed -i '/rend.Resolution =/c\rend.Resolution = 1200' "${CONF_DIR}/${FLYCAST_INI}"
        elif [ "$IRES" = "5" ]; then
                sed -i '/rend.Resolution =/c\rend.Resolution = 1440' "${CONF_DIR}/${FLYCAST_INI}"
        else
                sed -i '/rend.Resolution =/c\rend.Resolution = 480' "${CONF_DIR}/${FLYCAST_INI}"
        fi

  #Scan out render size, rend.Resolution is in lines (480 = 1x)
        SCANOUT_SCALE=$(scanout_internal_scale "$(awk '/^rend.Resolution = / {print $3 / 480; exit}' "${CONF_DIR}/${FLYCAST_INI}")" 480 0.5 9 0.25)
        sed -i "/rend.Resolution =/c\rend.Resolution = $(awk -v s="${SCANOUT_SCALE}" 'BEGIN { printf "%d", s * 480 }')" "${CONF_DIR}/${FLYCAST_INI}"
        grep -q "^rend.EmulateFramebuffer = yes" "${CONF_DIR}/${FLYCAST_INI}" && SCANOUT_SCALE=1
        case "$ASPECT" in w) SCANOUT_ASPECT=16:9 ;; sw) SCANOUT_ASPECT=0 ;; *) SCANOUT_ASPECT=4:3 ;; esac
        scanout_render_size 480 "${SCANOUT_SCALE}" "${SCANOUT_ASPECT}"

  #Graphics Renderer
        if [ "$GRENDERER" = "opengl" ]; then
                sed -i '/^pvr.rend =/c\pvr.rend = 0' "${CONF_DIR}/${FLYCAST_INI}"
        elif [ "$GRENDERER" = "vulkan" ]; then
                sed -i '/^pvr.rend =/c\pvr.rend = 4' "${CONF_DIR}/${FLYCAST_INI}"
        else
		sed -i '/^pvr.rend =/c\pvr.rend = @GRENDERER@' "${CONF_DIR}/${FLYCAST_INI}"
	fi

  #ShowFPS
        if [ "$FPS" = "1" ]; then
                sed -i '/^rend.ShowFPS =/c\rend.ShowFPS = yes' "${CONF_DIR}/${FLYCAST_INI}"
	else
		sed -i '/^rend.ShowFPS =/c\rend.ShowFPS = no' "${CONF_DIR}/${FLYCAST_INI}"
        fi

  #Vsync
        if [ "$VSYNC" = "1" ];then
                sed -i '/^rend.vsync =/c\rend.vsync = yes' "${CONF_DIR}/${FLYCAST_INI}"
	else
		sed -i '/^rend.vsync =/c\rend.vsync = no' "${CONF_DIR}/${FLYCAST_INI}"
        fi

# Asgard: widescreen cheats, integer scaling (unset = the emulator's own value)
WIDESCREEN_CHEATS=$(get_setting widescreen_cheats "${PLATFORM}" "${GAME}")
case "${WIDESCREEN_CHEATS}" in
  1) sed -i '/^rend.WidescreenGameHacks =/c\rend.WidescreenGameHacks = yes' "${CONF_DIR}/${FLYCAST_INI}" ;;
  0) sed -i '/^rend.WidescreenGameHacks =/c\rend.WidescreenGameHacks = no' "${CONF_DIR}/${FLYCAST_INI}" ;;
esac
INTEGER_SCALING=$(get_setting integer_scaling "${PLATFORM}" "${GAME}")
case "${INTEGER_SCALING}" in
  1) sed -i '/^rend.IntegerScale =/c\rend.IntegerScale = yes' "${CONF_DIR}/${FLYCAST_INI}" ;;
  0) sed -i '/^rend.IntegerScale =/c\rend.IntegerScale = no' "${CONF_DIR}/${FLYCAST_INI}" ;;
esac

#Retroachievements
/usr/bin/cheevos_flycast.sh

# Debugging info:
  echo "GAME set to: ${GAME}"
  echo "PLATFORM set to: ${PLATFORM}"
  echo "CONF DIR: ${CONF_DIR}/${FLYCAST_INI}"
  echo "CPU CORES set to: ${EMUPERF}"
  echo "ASPECT RATIO set to: ${ASPECT}"
  echo "AUTO FRAME SKIP set to: ${ASKIP}"
  echo "INTERNAL RESOLUTION set to: ${IRES}"
  echo "GRAPHICS RENDERER set to: ${GRENDERER}"
  echo "FPS set to: ${FPS}"
  echo "VSYNC set to: ${VSYNC}"
  echo "Launching /usr/bin/flycast ${1}"

#Run flycast emulator
$GPTOKEYB "flycast" -c "${CONF_DIR}/flycast.gptk" &
${EMUPERF} /usr/bin/flycast "${1}"
kill -9 "$(pidof gptokeyb)"
