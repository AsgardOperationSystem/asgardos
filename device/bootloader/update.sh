#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# Copyright (C) 2024-present ROCKNIX (https://github.com/ROCKNIX)

[ -z "$SYSTEM_ROOT" ] && SYSTEM_ROOT=""
[ -z "$BOOT_ROOT" ] && BOOT_ROOT="/flash"
[ -z "$BOOT_PART" ] && BOOT_PART=$(df "$BOOT_ROOT" | tail -1 | awk {' print $1 '})

# identify the boot device
if [ -z "$BOOT_DISK" ]; then
  case $BOOT_PART in
    /dev/mmcblk*) BOOT_DISK=$(echo $BOOT_PART | sed -e "s,p[0-9]*,,g");;
  esac
fi

# mount $BOOT_ROOT rw
mount -o remount,rw $BOOT_ROOT

# The partitions this device boots, as its entry names them now: an SD card's own labels, an internal install's, or
# whatever it was set up with. The new entry keeps them (UPD-8), so an update never points a card at an internal
# install's partitions, or the reverse.
ENTRY="$BOOT_ROOT/loader/entries/asgardos.conf"
KEEP=""
[ -f "$ENTRY" ] && KEEP=$(sed -n 's/^options[[:space:]]//p' "$ENTRY" | tr -s ' \t' '\n\n' | grep -E '^(boot|disk)=.')

# AsgardOS boots through OpenABL's Boot Loader Spec: the entry, the device trees and the power-on logo (init has
# already written KERNEL, the kernel the entry names).
for d in dtbs loader logo; do
  if [ -d "$SYSTEM_ROOT/usr/share/bootloader/$d" ]; then
    mkdir -p $BOOT_ROOT/$d
    cp -rf $SYSTEM_ROOT/usr/share/bootloader/$d/. $BOOT_ROOT/$d/
  fi
done
for kv in $KEEP; do
  sed -i "/^options/ s|\([[:space:]]${kv%%=*}=\)[^[:space:]]*|\1${kv#*=}|" "$ENTRY"
done
# Left from ROCKNIX's ABL (KERNEL was its Android boot image) and from the first OpenABL layout.
rm -rf $BOOT_ROOT/rocknix_abl $BOOT_ROOT/Image.gz

# AsgardOS: an update never flashes abl_a/abl_b (ROCKNIX ran updateabl here). Flash OpenABL by hand with
# updateabl, after checking the backup in thor/rocknix-abl/.

### REMOVE IN THE FUTURE ###
# cleanup old boot files
[ -d "$BOOT_ROOT/boot" ] && rm -rf "$BOOT_ROOT/boot"
[ -d "$BOOT_ROOT/EFI" ] && rm -rf "$BOOT_ROOT/EFI"
# end

# mount $BOOT_ROOT ro
sync
mount -o remount,ro $BOOT_ROOT

echo "UPDATE" > /storage/.boot.hint
