#!/bin/bash
# Asgard OS: device checks (docs/testing.md, level 4), run over SSH after an update. Read-only (TEST-6): they stop if a
# game is playing, and nothing here sleeps, restarts or changes the Thor. Only `check` lines count towards coverage.
#   ./test-device.sh root@192.168.50.30
#   check "<spec rules>" "<what>" '<read-only command run on the Thor: exit 0 means it holds, 77 means no evidence yet>'
# "No evidence yet" is a SKIP, not a pass (TEST-4): no sleep this boot, no SD card, a setting that's off.
set -uo pipefail
HOST=${1:?usage: test-device.sh user@host}
pass=0 fail=0 skip=0
remote() { ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" "$1"; }
remote true || { echo "can't reach $HOST"; exit 2; }
playing=$(remote 'cat /run/thor-playing.txt 2>/dev/null')
[ -z "$playing" ] || { echo "a game is playing, stopping (TEST-6): $playing"; exit 2; }
# A disk that's failing is no place to run these, and their results would mean nothing: reads fail for reasons of their own.
storage=$(remote 'grep -q emergency_ro /proc/mounts && echo "/storage is flagged emergency_ro"; dmesg | grep -q "I/O error, dev sda" && echo "I/O errors on the UFS disk"')
[ -z "$storage" ] || { echo "the Thor's storage is failing, stopping: $storage"; exit 2; }
# Each check first looks for a game again, because one can start during the run. sway_config is what sway loaded: autostart
# regenerates the file on disk after sway has read it, so the file doesn't have Thor's rules.
PRELUDE='[ -z "$(cat /run/thor-playing.txt 2>/dev/null)" ] || exit 75
sway_config() { SWAYSOCK=/run/0-runtime-dir/sway-ipc.0.sock swaymsg -p -t get_config; }'
check() {
  remote "$PRELUDE
$3" >/dev/null 2>&1
  case $? in
    75) echo "a game started, stopping (TEST-6)"; echo "$pass passed, $fail failed, $skip skipped, the rest not run"; exit 2 ;;
    0) pass=$((pass + 1)); printf 'PASS  %-18s %s\n' "$1" "$2" ;;
    77) skip=$((skip + 1)); printf 'SKIP  %-18s %s\n' "$1" "$2" ;;
    *) fail=$((fail + 1)); printf 'FAIL  %-18s %s\n' "$1" "$2" ;;
  esac
}

# Boot and the image
check "UPD-1" "the root filesystem is a read-only squashfs" 'grep -qE "^[^ ]+ / squashfs ro[, ]" /proc/mounts'
check "UPD-1" "/flash is mounted read-only" 'grep -qE "^[^ ]+ /flash [^ ]+ ro[, ]" /proc/mounts'
check "UPD-1" "/storage is mounted read-write" 'grep -qE "^[^ ]+ /storage [^ ]+ rw[, ]" /proc/mounts'
check "UPD-5" "the boot entry's kernel and device tree exist on /flash" 'e=/flash/loader/entries/asgardos.conf; k=$(sed -n "s/^linux  *//p" $e); d=$(sed -n "s/^devicetree  *//p" $e); [ -n "$k" ] && [ -n "$d" ] && [ -s "/flash$k" ] && [ -s "/flash$d" ]'
check "UPD-5" "the labels the boot entry names exist" 'e=/flash/loader/entries/asgardos.conf; grep -q "boot=LABEL=ASGARDOS" $e && grep -q "disk=LABEL=STORAGE" $e && [ -e /dev/disk/by-label/ASGARDOS ] && [ -e /dev/disk/by-label/STORAGE ]'
check "DEV-16" "the running image holds no baked-in Wi-Fi or SSH keys" '[ ! -e /usr/config/iwd ] && [ ! -e /usr/config/ssh/authorized_keys ]'
check "DEV-18" "test files don't ship" '[ -z "$(ls /usr/share/asgard/test_* 2>/dev/null)" ]'

# Asgard Home
check "HOME-7" "Asgard Home runs in a UTF-8 locale" 'tr "\0" "\n" < /proc/$(pidof -s asgard-home)/environ | grep -q "^LANG=C.UTF-8$" && test -d /storage/.cache/locpath/C.UTF-8'
check "HOME-3" "the library file Home reads is there" 'test -s /usr/config/emulationstation/es_systems.cfg'
check "OLED-2" "the panel driver exposes Ultra Black, and it matches the saved setting" 'v=$(cat /sys/module/panel_chipone_icna35xx/parameters/ultra_black); [ "$(sed -n "s/^asgard\.ultra_black=//p" /storage/.config/system/configs/system.cfg | tail -1)" = 0 ] && [ "$v" = N ] || [ "$v" = Y ]'
check "OLED-3" "the idle blanker is running" 'systemctl is-active -q thor-idle-blank'
check "MENU-1 PANEL-1" "the button daemon is running, and Home is listening on its command FIFO" 'pidof -s python3 >/dev/null && ps -ef | grep "[t]hor_ayn_button" >/dev/null && test -p /run/asgard-home.cmd'
check "PANEL-1" "the panel's program is installed" 'test -x /usr/bin/asgard-panel && test -f /usr/share/asgard/thor_panel.py'
check "TXT-1" "the text prompt's helper and keyboard are installed" 'test -x /usr/share/asgard/thor_text_input.py && test -x /usr/bin/asgard-text-input'
check "TXT-3" "no text prompt was left behind, with the pad grabbed" '! pidof asgard-text-input'
check "SND-4" "pw-play is there to play menu sounds, and the sounds are installed" 'command -v pw-play >/dev/null && test -f /usr/share/asgard-home/qml/sounds/select.wav'
check "SND-5" "asgard-osd is installed, and input_sense calls it" 'test -x /usr/share/asgard/asgard-osd && grep -q /usr/share/asgard/asgard-osd "$(command -v input_sense)"'
check "TOOL-1" "the Tools entries exist and point at programs that exist" 'for t in Firefox Files Moonlight Terminal; do test -x /storage/.config/gmu/playlists/$t.sh || exit 1; done; test -x /usr/bin/asgard-files && test -x /usr/bin/asgard-music && test -x /usr/bin/asgard-osk'
check "NET-1" "the programs Settings runs for the network are there" 'for c in wifictl asgardos-bluetooth usbgadget nmcli; do command -v $c >/dev/null || exit 1; done'
check "NET-2" "the VPN programs Settings runs are there" 'test -x /usr/sbin/tailscale && test -x /usr/sbin/zerotier-cli'

# Running games
check "GAME-1 EMU-4" "the launcher is in place and wraps the emulator with the game's profile and crash log" 'test -x /usr/bin/runemu.sh && grep -q "asgard-perf-profile.sh apply" /usr/bin/runemu.sh && grep -q asgard-crashlog.sh /usr/bin/runemu.sh && test -x /usr/bin/start_azahar.sh && test -x /usr/bin/start_melonds.sh'
check "GAME-2" "with no game running, the kill data names no game" '! test -s /tmp/.process-kill-data || ! grep -qv "^emulationstation$" /tmp/.process-kill-data'
check "GAME-4" "no game shows as playing, in the JSON either, and the writer is installed" '! test -e /run/thor-playing.json && test -f /usr/share/asgard/playlog.py'
check "GAME-6" "Back to Home's script and what it runs are there, and nothing waits frozen" 'test -f /usr/share/asgard/asgard-background.py && command -v killall >/dev/null && command -v pidof >/dev/null && ! test -e /run/asgard-bg.json'
check "GAME-7" "the sleep hook is installed, and Home is listening on the FIFO it writes to" 'test -x /usr/lib/systemd/system-sleep/asgard-game-pause && test -p /run/asgard-home.cmd'
check "GAME-9" "InputPlumber is up and a virtual DualSense exists" 'systemctl is-active -q inputplumber && grep -qi "Vendor=054c" /proc/bus/input/devices'
check "GAME-9" "the raw Thor pad's event node is hidden from games" 'evs=$(awk "BEGIN{RS=\"\"} /rsinput-gamepad\/input0/" /proc/bus/input/devices | sed -n "s/^H: Handlers=.*\(event[0-9]*\).*/\1/p"); test -n "$evs" && for e in $evs; do test ! -e /dev/input/$e || test "$(stat -c %a /dev/input/$e)" = 0 || exit 1; done'
check "GAME-10" "sway has the top screen rule, and the idle-off script is installed" 'sway_config | grep -q "^# thor-fullscreen" && test -x /usr/share/asgard/thor-bottom-idle-off.sh'
check "COMP-1" "sway has the second-window rules: moved, powered on, rotated" 'sway_config | grep -q "GamePad).\*\"\] move window to output DSI-1" && sway_config | grep -q "GamePad).\*\"\] output DSI-1 power on" && sway_config | grep -q "^# thor-rotate" && test -x /usr/share/asgard/thor-bottom-rotate.sh'
check "COMP-2" "Eden Duo is installed and its companion rule is in sway" 'test -x /usr/bin/start_eden-duo.sh && sway_config | grep -q "^# thor-eden-duo"'
check "COMP-3" "lowerdeck is installed and vertical-check runs for RetroArch windows" 'test -f /usr/share/lowerdeck/main.py && sway_config | grep -q "^# thor-lowerdeck" && sway_config | grep -q "RetroArch.\*\"\] exec /usr/bin/vertical-check"'
check "COMP-4" "sway has the rules for the ports in /storage" 'for r in thor-wwhd thor-dusklight thor-love2 thor-lumidex; do sway_config | grep -q "^# $r" || exit 1; done'
check "OVR-2 OVR-5" "the option catalogue answers on the device, with the hardware rows and an emulator's own" 'o=$(python3 /usr/share/asgard/thor_settings.py --features azahar azahar-sa); for k in cpu_cap_mid gpu_cap fan_mode motion eq_speaker sleep_mode screen_layout; do echo "$o" | grep -q "\"$k\"" || exit 1; done'
check "OVR-3" "the shader cache script is installed" 'test -x /usr/share/asgard/asgard-shader-cache.sh'
check "GPU-1" "the row's default has a version to name" 'test -s /usr/share/mesa/version'
check "GPU-2" "the extra Turnip is installed, and its icd.json points at a library that exists" 'j=/usr/lib/gpu-drivers/mesa-25.3.6/icd.json; test -f $j && test -f "$(sed -n "s/.*\"library_path\": \"\([^\"]*\)\".*/\1/p" $j)"'
check "GPU-3" "Mesa has Zink" 'test -e /usr/lib/dri/zink_dri.so'
check "GPU-3" "Zink is the default: Home, whose environment games inherit, has the override" 'tr "\0" "\n" < /proc/$(pidof -s asgard-home)/environ | grep -qx "MESA_LOADER_DRIVER_OVERRIDE=zink"'
check "PORT-1" "PortMaster is installed" 'test -x /usr/bin/start_portmaster.sh'
check "PORT-3" "the linker can find libtheoradec" 'test -e /usr/lib/libtheoradec.so.1'
check "EMU-1 EMU-5" "the image has its systems and option catalogue, and no EmulationStation" 'test "$(grep -c "<system>" /usr/config/emulationstation/es_systems.cfg)" -ge 100 && test -s /usr/share/asgard/es_features.cfg && ! command -v emulationstation >/dev/null'
check "BAT-3" "the screens-off script is installed, and the power handler knows the marker" 'test -x /usr/share/asgard/asgard-screens-off.sh && grep -q /run/asgard-keep-running /usr/lib/autostart/quirks/platforms/SM8550/bin/power-handler'

# Settings, performance, sound, input
check "CFG-7" "the sensor server runs only if sensors-root is there" '[ -e /storage/.config/asgard/sensors-root/hexagonrpc.json ] || ! systemctl is-active -q thor-sensorspd'
check "CFG-8" "the root login's hash matches root.password" '. /etc/profile.d/001-functions; p=$(get_setting root.password); h=$(sed -n "s/^root:\([^:]*\):.*/\1/p" /storage/.cache/shadow); s=${h%\$*}; [ -n "$p" ] && [ "$(cryptpw -m sha512 -S "${s##*\$}" "$p")" = "$h" ]'
check "PERF-1" "three core types: policy0 CPU0-2, policy3 CPU3-6, policy7 CPU7" 'P=/sys/devices/system/cpu/cpufreq; [ "$(echo $(cat $P/policy0/related_cpus))" = "0 1 2" ] && [ "$(echo $(cat $P/policy3/related_cpus))" = "3 4 5 6" ] && { [ "$(cat /sys/devices/system/cpu/cpu7/online)" = 0 ] || [ "$(echo $(cat $P/policy7/related_cpus))" = "7" ]; }'
check "PERF-1 PERF-3" "in Home each type's clock is a supported step at or under the menu's cap" '. /etc/profile.d/001-functions; P=/sys/devices/system/cpu/cpufreq; for x in little:0:90 mid:3:75 prime:7:75; do t=${x%%:*}; r=${x#*:}; pol=${r%:*}; d=${r#*:}; c=$(get_setting asgard.cpu_cap.$t); [ "$c" = off ] && continue; [ "$(get_setting asgard.cpu_cap)" = 0 ] && d=100; c=${c:-$d}; f=$(cat $P/policy$pol/scaling_max_freq); [ "$f" -le $(( $(cat $P/policy$pol/cpuinfo_max_freq) * c / 100 )) ] || exit 1; tr " " "\n" < $P/policy$pol/scaling_available_frequencies | grep -qx "$f" || exit 1; done'
check "PERF-4" "in Home the GPU's clock is a supported step at or under the menu's cap" '. /etc/profile.d/001-functions; G=/sys/class/devfreq/3d00000.gpu; c=$(get_setting asgard.gpu_cap); c=${c:-100}; f=$(cat $G/max_freq); s=$(tr " " "\n" < $G/available_frequencies | sort -n); t=$(echo "$s" | tail -1); { [ "$f" -le $(( t * c / 100 )) ] || [ "$f" = "$(echo "$s" | head -1)" ]; } && tr " " "\n" < $G/available_frequencies | grep -qx "$f"'
check "PERF-5" "fancontrol's unit runs asgard-fan.sh, and a fixed speed is what the fan has" '. /etc/profile.d/001-functions; systemctl cat fancontrol | grep -q "^ExecCondition=/usr/share/asgard/asgard-fan.sh" || exit 1; m=$(get_setting asgard.fan_manual); [ -z "$m" ] || [ "$(cat $(ls /sys/class/hwmon/hwmon*/pwm1 | head -1))" = "$m" ]'
check "PWR-8" "the gyro service runs only if the menu asked for it" '. /etc/profile.d/001-functions; m=$(get_setting asgard.motion); if [ "$m" = 1 ] || [ "$m" = on ]; then [ ! -e /storage/.config/asgard/sensors-root/hexagonrpc.json ] || systemctl is-active -q asgard-motiond; else ! systemctl is-active -q asgard-motiond; fi'
check "PWR-11" "system.suspendmode is one Settings offers, or unset" '. /etc/profile.d/001-functions; case "$(get_setting system.suspendmode)" in ""|mem|freeze|off) ;; *) exit 1 ;; esac'
check "INP-1" "while the gyro service runs, it serves DSU on 127.0.0.1:26760" 'systemctl is-active -q asgard-motiond || exit 0; grep -q "0100007F:6888 " /proc/net/udp'
check "INP-2" "the stick lights' commands and LEDs are there" 'command -v ledcontrol && command -v analog_sticks_ledcontrol && [ -d /sys/devices/platform/multi-ledl1 ] && [ -d /sys/devices/platform/multi-ledr1 ]'
check "AUD-1" "the rule that puts headphones first is installed" 'grep -q "priority.session = 1100" /usr/share/wireplumber/wireplumber.conf.d/60-thor-headphones-first.conf'
check "AUD-2" "every EQ filter sink is at 100 %" '. /etc/profile.d/001-functions; for f in $(pactl list short sinks | awk "\$2 ~ /^thor_dsp_/ {print \$2}"); do [ "$(pactl get-sink-volume "$f" | grep -o "[0-9]*%" | sort -u)" = "100%" ] || exit 1; done'
check "SCR-4" "both touchscreens are on their own panels, with a matrix each, in sway's config" 'sway_config | grep -q "input \"0:0:top_touchscreen\" map_to_output DSI-2" && sway_config | grep -q "input \"0:0:bottom_touchscreen\" map_to_output DSI-1" && sway_config | grep -q "input \"0:0:top_touchscreen\" calibration_matrix" && sway_config | grep -q "input \"0:0:bottom_touchscreen\" calibration_matrix" && sway_config | grep -q "^output DSI-1 transform 90"'
check "SCR-5" "the running kernel booted quiet, and the boot animation is enabled" 'grep -qw quiet /proc/cmdline && grep -qw loglevel=1 /proc/cmdline && grep -qw systemd.show_status=false /proc/cmdline && ls /usr/lib/systemd/system/*.wants/asgard-bootanim.service'

# Power, battery, diagnostics, kernel
check "PWR-1" "suspend to RAM means s2idle" 'grep -q "\[s2idle\]" /sys/power/mem_sleep'
check "PWR-1" "AOSS collapsed in this boot's sleeps" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; [ "$(sed -n "s/^Count: //p" /sys/kernel/debug/qcom_stats/aosd)" -gt 0 ]'
check "PWR-1 KERN-7" "CX collapsed in this boot's sleeps, which LPASS would block" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; [ "$(sed -n "s/^Count: //p" /sys/kernel/debug/qcom_stats/cxsd)" -gt 0 ]'
check "PWR-1 KERN-6" "DDR collapsed in this boot's sleeps, which a GPU vote would block" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; [ "$(sed -n "s/^Count: //p" /sys/kernel/debug/qcom_stats/ddr)" -gt 0 ]'
check "PWR-1" "the last sleep of 60 s or more in the audit log collapsed (needs asgard.sleep_audit=1)" '[ -s /storage/sleep-audit.csv ] || exit 77; awk -F, '\''NR == 1 { for (i = 1; i <= NF; i++) c[$i] = i; next } $c["secs"] >= 60 { seen = 1; ok = $c["cxsd_cnt"] > 0 && $c["aosd_cnt"] > 0 && $c["ddr_cnt"] > 0 } END { exit seen ? !ok : 77 }'\'' /storage/sleep-audit.csv'
check "PWR-3 KERN-2" "after a sleep this boot the pad's stream runs, at the rate asgard-pad-fix wants" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; a=$(awk "/qcom_geni_serial_uart2/{print \$2}" /proc/interrupts); sleep 2; b=$(awk "/qcom_geni_serial_uart2/{print \$2}" /proc/interrupts); [ $(((b - a) / 2)) -ge 20 ]'
check "KERN-2" "asgard-pad-fix's last word isn't that it gave up" '[ -s /storage/pad-fix.log ] || exit 0; ! tail -1 /storage/pad-fix.log | grep -q "still stalled"'
check "PWR-3 KERN-5" "after a sleep this boot Wi-Fi is up, so its link retrained" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; [ "$(cat /sys/class/net/wlan0/operstate)" = up ]'
check "PWR-3 KERN-7" "after a sleep this boot the sound card is there" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; grep -q "^ *0 \[" /proc/asound/cards'
check "PWR-3" "after a sleep this boot /storage is still read-write" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; grep " /storage " /proc/mounts | grep -qE " rw[ ,]"'
check "PWR-3" "the RTC can wake it" '[ "$(cat /sys/class/rtc/rtc0/device/power/wakeup)" = enabled ]'
check "PWR-9" "no alarm is armed for a wake while awake" '[ -z "$(cat /sys/class/rtc/rtc0/wakealarm)" ]'
check "PWR-9" "no loaded timer wakes the system" '! systemctl show "*.timer" -p WakeSystem | grep -q "=yes"'
check "PWR-9" "windows draw at most 5 frames in 5 s with nothing changing (leave the Thor alone on Home)" 'SWAYSOCK=/run/0-runtime-dir/sway-ipc.0.sock python3 -c '\''
import json, subprocess, sys, time
def frames():
    tree, total, stack = json.loads(subprocess.check_output(["swaymsg", "-t", "get_tree", "-r"])), None, []
    stack.append(tree)
    while stack:
        n = stack.pop()
        stack += n.get("nodes", []) + n.get("floating_nodes", [])
        if "frames" in n:
            total = (total or 0) + n["frames"]
    return total
a = frames(); time.sleep(5); b = frames()
sys.exit(0 if a is not None and b - a <= 5 else 1)'\'''
check "PWR-10" "logind suspends on the lid after a 10 s holdoff, and leaves the key to power-handler" '[ "$(busctl get-property org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager HoldoffTimeoutUSec)" = "t 10000000" ] && [ "$(busctl get-property org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager HandleLidSwitch)" = "s \"suspend\"" ] && [ "$(busctl get-property org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager HandlePowerKey)" = "s \"ignore\"" ]'
check "PWR-10" "input_sense finds the power handler, and suspend isn't switched off" '[ -x /usr/lib/autostart/quirks/platforms/SM8550/bin/power-handler ] && . /etc/profile && [ "$(get_setting system.suspendmode)" != off ]'
check "PWR-12" "the hook is installed, its pad device exists, InputPlumber runs" '[ -x /usr/lib/systemd/system-sleep/asgard-pad-fix ] && [ -e /sys/bus/serial/drivers/rsinput/serial1-0 ] && systemctl is-active -q inputplumber'
check "BAT-2 KERN-8" "with bypass on above 20 %, the charge current has been set to 0 and stays there (needs asgard.bypass_charging=1)" '[ "$(sed -n "s/^asgard\.bypass_charging=//p" /storage/.config/system/configs/system.cfg | tail -1)" = 1 ] && [ "$(cat /sys/class/power_supply/battery/capacity)" -gt 20 ] || exit 77; [ "$(cat /sys/class/power_supply/battery/constant_charge_current)" = 0 ]'
check "LOG-2" "this boot is marked as running, and no more than 10 reports are kept" 'systemctl is-active -q asgard-lastboot && [ -e /storage/.cache/asgard-running ] && [ "$(ls /storage/.config/thor/freezes 2>/dev/null | wc -l)" -le 10 ]'
check "LOG-3" "a crash goes to systemd-coredump, whose directory is /storage/.cache/cores" 'command -v coredumpctl && grep -q systemd-coredump /proc/sys/kernel/core_pattern && systemctl is-active -q asgard-cores && grep -q " /var/lib/systemd/coredump " /proc/self/mountinfo'
check "LOG-6" "the logger runs, its last line is under 2 minutes old, and the log is at most 5 MB plus a line" 'systemctl is-active -q thor-battery-log && [ $(($(date +%s) - $(tail -1 /storage/battery-log.csv | cut -d, -f1))) -lt 120 ] && [ "$(stat -c %s /storage/battery-log.csv)" -lt 5243904 ]'
check "LOG-6" "the logger has used under 1 % of one core since it started, children included" 'p=$(systemctl show -p MainPID --value thor-battery-log); [ "$p" -gt 0 ] || exit 1; u=$(cut -d" " -f1 /proc/uptime); awk -v up="$u" -v hz="$(getconf CLK_TCK)" '\''{ cpu = ($14 + $15 + $16 + $17) / hz; run = up - $22 / hz; exit !(run > 60 && cpu / run < 0.01) }'\'' /proc/$p/stat'
check "KERN-1" "both panels offer 60 and 120 Hz" 'SWAYSOCK=/run/0-runtime-dir/sway-ipc.0.sock swaymsg -t get_outputs -r | python3 -c '\''
import json, sys
dsi = [o for o in json.load(sys.stdin) if o["name"].startswith("DSI-")]
sys.exit(0 if len(dsi) == 2 and all({60, 120} <= {round(m["refresh"] / 1000) for m in o["modes"]} for o in dsi) else 1)'\'''
check "KERN-1" "both touchscreens are bound, and Ultra Black is switchable" '[ "$(ls /sys/bus/i2c/drivers/edt_ft5x06 | grep -c "^[0-9]")" = 2 ] && [ -r /sys/module/panel_chipone_icna35xx/parameters/ultra_black ]'
check "KERN-3" "UFS reaches HS-G5 under a read (the gear scales down when idle)" 'g=/sys/bus/platform/devices/1d84000.ufshc/power_info/gear; dd if=/dev/sda of=/dev/null bs=1M count=1024 iflag=direct 2>/dev/null & d=$!; for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do [ "$(cat $g)" = HS_GEAR5 ] && { kill $d 2>/dev/null; exit 0; }; sleep 0.2; done; kill $d 2>/dev/null; exit 1'
check "KERN-3" "no PHY calibration failure in this boot" '! dmesg | grep -q "Failed to calibrate PHY"'
check "KERN-3" "an SD card runs at SDR104 (needs a UHS-I card in)" 'ls /sys/block | grep -q "^mmcblk" || exit 77; grep -qh "sd uhs SDR104" /sys/kernel/debug/mmc*/ios'
check "KERN-4" "USB resumes cleanly: no failed resume this boot" '! dmesg | grep -q "dwc3_qcom_pm_resume returns"'
check "KERN-4" "with no cable the USB controller is runtime-suspended, so its DDR vote is gone" '[ "$(cat /sys/class/power_supply/qcom-battmgr-usb/online)" = 0 ] || exit 77; [ "$(cat /sys/bus/platform/devices/a600000.usb/power/control)" = auto ] && [ "$(cat /sys/bus/platform/devices/a600000.usb/power/runtime_status)" = suspended ]'
check "KERN-4" "the USB-C connector is a wake source" '[ "$(cat /sys/bus/auxiliary/devices/pmic_glink.ucsi.0/power/wakeup)" = enabled ]'
check "KERN-5" "after a sleep this boot the Wi-Fi PCIe GDSC has been off, and only endpoints veto D3cold" '[ "$(cat /sys/power/suspend_stats/success)" -gt 0 ] || exit 77; [ "$(cat /sys/module/pci_host_common/parameters/endpoint_d3cold)" = Y ] && awk '\''NR > 1 && $3 > 0 { on = 1 } END { exit !on }'\'' /sys/kernel/debug/pm_genpd/pcie_0_gdsc/idle_states'
check "KERN-8" "the charge current can be set, and its service runs" 'b=/sys/class/power_supply/battery; [ -w $b/constant_charge_current ] && [ "$(cat $b/constant_charge_current_max)" -gt 0 ] && systemctl is-active -q asgard-charge-limit'

echo "$pass passed, $fail failed, $skip skipped"
[ "$fail" = 0 ]
