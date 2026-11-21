#!/bin/bash
# spec: UPD-8
# A copy of automount on fake disks (blkid, mount and /proc stubbed): the games-card search never takes a partition an
# install boots from or keeps its /storage on (ASGARDOS/STORAGE, ASGARDSD/STORAGESD, ROCKNIX), so an Asgard card next to
# an internal install, or a ROCKNIX card in an internal Asgard, isn't mounted as games storage. A plain games card still is.
set -e
H=$(dirname "$(readlink -f "$0")")
SCRIPT="$H/../../asgardos/sources/scripts/automount"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

run() {   # run <name>: automount with the disks in $T/<name>.blkid (dev label type) and $T/<name>.mounted (devs mounted)
  local D="$T/$1"; rm -rf "$D"; mkdir -p "$D/bin" "$D/storage" "$D/sysblock"
  cp "$T/$1.blkid" "$D/disks"; : > "$D/mounts"
  while read -r dev; do echo "$dev /somewhere ext4 rw 0 0" >> "$D/mounts"; done < "$T/$1.mounted"
  : > "$D/partitions"
  while read -r dev label type size; do echo " 8 0 $size ${dev#/dev/}" >> "$D/partitions"; done < "$D/disks"
  echo " 179 0 1000000000 mmcblk0" >> "$D/partitions"   # the whole card, what the size check reads for mmcblk partitions
  cat > "$D/profile" <<EOF
log() { :; }
get_setting() { :; }
set_setting() { :; }
EOF
  cat > "$D/bin/blkid" <<EOF
#!/bin/bash
if [ "\$1" = -o ]; then   # blkid -o export DEV
  while read -r dev label type size; do [ "\$dev" = "\$3" ] && { echo "DEVNAME=\$dev"; [ "\$label" = - ] || echo "LABEL=\$label"; echo "TYPE=\$type"; }; done < "$D/disks"
else
  while read -r dev label type size; do
    if [ "\$label" = - ]; then echo "\$dev: TYPE=\"\$type\""; else echo "\$dev: LABEL=\"\$label\" TYPE=\"\$type\""; fi
  done < "$D/disks"
fi
EOF
  printf '#!/bin/sh\necho "mount $*" >> "%s/log"\n' "$D" > "$D/bin/mount"
  for c in umount lsmod modprobe systemctl systemd-tmpfiles fsck; do printf '#!/bin/sh\nexit 0\n' > "$D/bin/$c"; done
  printf '#!/bin/sh\nexit 0\n' > "$D/bin/mountpoint"
  chmod +x "$D/bin/"*
  sed -e "s#^\. /etc/profile#. $D/profile#" -e "s#^\. /etc/os-release##" -e "s#/usr/bin/busybox ##g" -e "s#/usr/sbin/fsck#fsck#g" \
      -e "s#/proc/partitions#$D/partitions#g" -e "s#/proc/mounts#$D/mounts#g" -e "s#/sys/class/block/#$D/sysblock/#g" \
      -e 's#\[ -e "\${DEV}" \]#true#' -e 's#\[ -e "\${1}" \]#true#' \
      -e "s#/storage#$D/storage#g" "$SCRIPT" > "$D/automount"   # the fake devices have no /dev nodes
  (cd "$D" && PATH="$D/bin:$PATH" bash "$D/automount" >/dev/null 2>&1) || true
  touch "$D/log"
}
mounted() { grep -q "^mount [^-]*$2 " "$T/$1/log"; }   # was <dev> mounted as the games card (not a --bind)?

# Booted from an Asgard card, Asgard (or ROCKNIX) on internal storage: its partitions aren't the card's games storage.
cat > "$T/card.blkid" <<EOF
/dev/mmcblk0p1 ASGARDSD vfat 1000000000
/dev/mmcblk0p2 STORAGESD ext4 1000000000
/dev/sda5 - ext4 32768
/dev/sda18 ASGARDOS vfat 2097152
/dev/sda19 STORAGE ext4 200000000
/dev/sdb1 ROCKNIX vfat 2097152
EOF
printf '/dev/mmcblk0p1\n/dev/mmcblk0p2\n' > "$T/card.mounted"
run card
if mounted card /dev/sda19; then echo "FAIL: an SD-booted Asgard took the internal STORAGE as its games card (UPD-8)"; exit 1; fi
if mounted card /dev/sdb1; then echo "FAIL: a ROCKNIX boot partition was taken as a games card"; exit 1; fi

# Internal Asgard, a ROCKNIX system card in the slot: not games storage either.
cat > "$T/rocknix.blkid" <<EOF
/dev/mmcblk0p1 ROCKNIX vfat 500000000
/dev/mmcblk0p2 STORAGE ext4 500000000
/dev/sda18 ASGARDOS vfat 2097152
/dev/sda19 STORAGE ext4 200000000
EOF
printf '/dev/sda18\n/dev/sda19\n' > "$T/rocknix.mounted"
run rocknix
if mounted rocknix /dev/mmcblk0p2 || mounted rocknix /dev/mmcblk0p1; then
  echo "FAIL: a ROCKNIX card's partition was taken as games storage"; exit 1
fi

# Internal Asgard, a plain games card: mounted as before.
cat > "$T/games.blkid" <<EOF
/dev/mmcblk0p1 - exfat 500000000
/dev/sda18 ASGARDOS vfat 2097152
/dev/sda19 STORAGE ext4 200000000
EOF
printf '/dev/sda18\n/dev/sda19\n' > "$T/games.mounted"
run games
mounted games /dev/mmcblk0p1 || { echo "FAIL: a plain games card wasn't mounted"; exit 1; }
echo ok
